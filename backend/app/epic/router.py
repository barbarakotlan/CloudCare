"""/epic/* routes: connect a patient's MyChart account and read their records.

The OAuth redirect lands on the Next.js site (it owns the registered redirect URI),
which forwards `code` + `state` here server to server. Tokens never leave the API.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.epic import crypto, store
from app.epic.config import EpicSettings, EpicUnavailable, discover, get_settings, normalize_base
from app.epic.fhir import EpicFhirClient, EpicRevoked, fetch_records
from app.epic.oauth import EpicOAuthError, build_authorize_url, exchange_code, revoke_token, utcnow
from app.epic.schemas import (
    ConnectCallbackIn,
    ConnectCallbackOut,
    ConnectStartOut,
    EpicRecordsOut,
    EpicStatusOut,
)
from app.models import User

log = logging.getLogger("cloudcare.epic")

router = APIRouter(prefix="/epic", tags=["epic"])

NOT_CONFIGURED = "MyChart connection isn't configured on this server yet"
NOT_CONNECTED = "MyChart is not connected"
RECONNECT = "MyChart access expired or was revoked. Reconnect MyChart to continue."

_warned_unconfigured = False


def epic_settings() -> EpicSettings:
    """503 until EPIC_CLIENT_ID and a valid EPIC_TOKEN_ENCRYPTION_KEY are set."""
    global _warned_unconfigured
    settings = get_settings()
    problem = None
    if settings.missing:
        problem = f"missing {', '.join(settings.missing)}"
    else:
        try:
            crypto.validate_key(settings.encryption_key)
        except crypto.TokenCryptoError:
            problem = "EPIC_TOKEN_ENCRYPTION_KEY is not a valid Fernet key"
    if problem:
        if not _warned_unconfigured:
            log.warning("epic.not_configured (%s); /epic routes return 503", problem)
            _warned_unconfigured = True
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED)
    return settings


def require_patient(user: User = Depends(get_current_user)) -> User:
    if user.role != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Patients only")
    return user


@router.post("/connect/start", response_model=ConnectStartOut)
def connect_start(
    settings: EpicSettings = Depends(epic_settings),
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    try:
        endpoints = discover(settings.fhir_base_url)
    except EpicUnavailable:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't reach Epic. Try again in a minute.")
    state, verifier = store.create_state(db, settings, user.id)
    log.info("epic.connect.start")
    return {"authorize_url": build_authorize_url(endpoints.authorization_endpoint, settings, state, verifier)}


@router.post("/connect/callback", response_model=ConnectCallbackOut)
def connect_callback(
    body: ConnectCallbackIn,
    settings: EpicSettings = Depends(epic_settings),
    db: Session = Depends(get_db),
):
    """No user token here: the single-use, 10-minute state identifies the patient.

    `detail` is always a short code; the Next.js callback turns it into ?reason=.
    """
    try:
        pending = store.consume_state(db, settings, body.state)
    except store.StateError as exc:
        log.info("epic.connect.callback.rejected reason=%s", exc.code)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.code)

    configured_iss = normalize_base(settings.fhir_base_url)
    if normalize_base(pending.iss) != configured_iss or (body.iss and normalize_base(body.iss) != configured_iss):
        log.warning("epic.connect.callback.rejected reason=iss_mismatch")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "iss_mismatch")
    if pending.redirect_uri != settings.redirect_uri:
        # The token request must repeat the exact redirect_uri used to authorize.
        log.warning("epic.connect.callback.rejected reason=redirect_uri_changed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri_mismatch")

    try:
        endpoints = discover(settings.fhir_base_url)
        tokens = exchange_code(endpoints.token_endpoint, settings, body.code, pending.code_verifier)
    except EpicUnavailable:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "epic_unreachable")
    except EpicOAuthError as exc:
        reason = exc.code if exc.code in ("no_patient", "unexpected_scope", "invalid_patient") else "token_exchange_failed"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, reason)

    if db.get(User, pending.user_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_state")
    conn = store.save_connection(db, settings, pending.user_id, configured_iss, tokens)
    log.info("epic.connect.callback.ok refresh_token=%s", bool(tokens.refresh_token))
    return {"ok": True, "patient_fhir_id": conn.patient_fhir_id}


@router.get("/status", response_model=EpicStatusOut)
def epic_status(
    settings: EpicSettings = Depends(epic_settings),
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    conn = store.get_connection(db, user.id)
    if conn is None:
        return EpicStatusOut(connected=False, sandbox=settings.sandbox)
    return EpicStatusOut(
        connected=conn.status == "active",
        patient_fhir_id=conn.patient_fhir_id,
        issuer=conn.iss,
        connected_at=conn.connected_at,
        scopes=conn.scope.split() if conn.scope else [],
        last_sync_at=conn.last_sync_at,
        revoked=conn.status == "revoked",
        sandbox=settings.sandbox,
    )


@router.get("/records", response_model=EpicRecordsOut)
def epic_records(
    settings: EpicSettings = Depends(epic_settings),
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Fetched live from Epic on every call; nothing clinical is stored."""
    conn = store.get_connection(db, user.id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_CONNECTED)
    if conn.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, RECONNECT)

    try:
        access = store.access_token(conn, settings)
        refresh = store.refresh_token(conn, settings)
    except crypto.TokenCryptoError:
        # Key was rotated: the stored tokens are unusable, so treat it like a revoke.
        store.mark_revoked(db, conn)
        raise HTTPException(status.HTTP_409_CONFLICT, RECONNECT)

    def persist(tokens):
        store.apply_tokens(conn, settings, tokens)
        db.commit()

    try:
        with EpicFhirClient(
            settings=settings,
            patient_id=conn.patient_fhir_id,
            access_token=access,
            refresh_token=refresh,
            expires_at=conn.expires_at,
            on_tokens=persist,
        ) as client:
            records = fetch_records(client)
    except EpicRevoked:
        store.mark_revoked(db, conn)
        raise HTTPException(status.HTTP_409_CONFLICT, RECONNECT)
    except EpicUnavailable:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't reach Epic. Try again in a minute.")

    fetched_at = utcnow()
    store.touch_sync(db, conn, fetched_at)
    return {**records, "fetched_at": fetched_at}


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def epic_disconnect(
    settings: EpicSettings = Depends(epic_settings),
    user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    conn = store.get_connection(db, user.id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_CONNECTED)

    # Best effort: only if Epic advertises a revocation endpoint (the sandbox doesn't).
    try:
        endpoints = discover(settings.fhir_base_url)
        if endpoints.revocation_endpoint:
            token = store.refresh_token(conn, settings)
            hint = "refresh_token"
            if not token:
                token, hint = store.access_token(conn, settings), "access_token"
            revoke_token(endpoints.revocation_endpoint, settings, token, hint)
    except (EpicUnavailable, crypto.TokenCryptoError):
        pass

    store.delete_connection(db, conn)
    log.info("epic.connection.deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
