"""Database side of the Epic connection: pending authorize states and stored tokens.

Every lookup of a connection goes through the CloudCare user id, so one patient can
never reach another patient's row.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.epic import crypto
from app.epic.config import EpicSettings
from app.epic.oauth import STATE_TTL, TokenSet, as_utc, new_code_verifier, new_state, utcnow
from app.models.epic import EpicConnection, EpicOAuthState

log = logging.getLogger("cloudcare.epic")


# ---- authorize states ----------------------------------------------------------------


def create_state(db: Session, settings: EpicSettings, user_id: uuid.UUID) -> tuple[str, str]:
    """Stores a fresh state + PKCE verifier for this user. Returns (state, verifier)."""
    now = utcnow()
    # Old attempts by this user and anything expired are no longer useful.
    db.execute(delete(EpicOAuthState).where(EpicOAuthState.user_id == user_id))
    db.execute(delete(EpicOAuthState).where(EpicOAuthState.expires_at < now))
    state = new_state()
    verifier = new_code_verifier()
    db.add(
        EpicOAuthState(
            state=state,
            user_id=user_id,
            code_verifier=crypto.encrypt(verifier, settings.encryption_key),
            iss=settings.fhir_base_url,
            redirect_uri=settings.redirect_uri,
            created_at=now,
            expires_at=now + STATE_TTL,
        )
    )
    db.commit()
    return state, verifier


class StateError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ConsumedState:
    user_id: uuid.UUID
    code_verifier: str
    iss: str
    redirect_uri: str


def consume_state(db: Session, settings: EpicSettings, state: str) -> ConsumedState:
    """Deletes the state row and returns what it held. A state works exactly once.

    The DELETE ... RETURNING is atomic, so two callbacks racing with the same state
    can't both succeed.
    """
    if not state or len(state) > 128:
        raise StateError("invalid_state")
    row = db.execute(
        delete(EpicOAuthState)
        .where(EpicOAuthState.state == state)
        .returning(
            EpicOAuthState.user_id,
            EpicOAuthState.code_verifier,
            EpicOAuthState.iss,
            EpicOAuthState.redirect_uri,
            EpicOAuthState.expires_at,
        )
    ).first()
    db.commit()
    if row is None:
        raise StateError("invalid_state")
    if as_utc(row.expires_at) <= utcnow():
        raise StateError("expired_state")
    try:
        verifier = crypto.decrypt(row.code_verifier, settings.encryption_key)
    except crypto.TokenCryptoError:
        raise StateError("invalid_state")
    return ConsumedState(user_id=row.user_id, code_verifier=verifier, iss=row.iss, redirect_uri=row.redirect_uri)


# ---- connections ------------------------------------------------------------------------


def get_connection(db: Session, user_id: uuid.UUID) -> EpicConnection | None:
    return db.scalar(select(EpicConnection).where(EpicConnection.user_id == user_id))


def save_connection(db: Session, settings: EpicSettings, user_id: uuid.UUID, iss: str, tokens: TokenSet) -> EpicConnection:
    """Creates or replaces this user's connection with freshly issued tokens."""
    conn = get_connection(db, user_id)
    if conn is None:
        conn = EpicConnection(user_id=user_id)
        db.add(conn)
    conn.iss = iss
    conn.patient_fhir_id = tokens.patient or ""
    conn.connected_at = utcnow()
    conn.last_sync_at = None
    conn.status = "active"
    conn.id_token_sub = tokens.id_token_sub
    apply_tokens(conn, settings, tokens)
    db.commit()
    db.refresh(conn)
    return conn


def apply_tokens(conn: EpicConnection, settings: EpicSettings, tokens: TokenSet) -> None:
    """Writes new tokens onto the row (caller commits). Keeps the old refresh token
    when a refresh response doesn't rotate it."""
    conn.access_token_enc = crypto.encrypt(tokens.access_token, settings.encryption_key)
    if tokens.refresh_token:
        conn.refresh_token_enc = crypto.encrypt(tokens.refresh_token, settings.encryption_key)
    conn.token_type = tokens.token_type
    if tokens.scope:
        conn.scope = tokens.scope
    elif not conn.scope:
        conn.scope = settings.scopes
    conn.expires_at = tokens.expires_at


def access_token(conn: EpicConnection, settings: EpicSettings) -> str:
    return crypto.decrypt(conn.access_token_enc, settings.encryption_key)


def refresh_token(conn: EpicConnection, settings: EpicSettings) -> str | None:
    return crypto.decrypt_optional(conn.refresh_token_enc, settings.encryption_key)


def mark_revoked(db: Session, conn: EpicConnection) -> None:
    conn.status = "revoked"
    db.commit()
    log.info("epic.connection.revoked")


def touch_sync(db: Session, conn: EpicConnection, when: datetime | None = None) -> None:
    conn.last_sync_at = when or utcnow()
    db.commit()


def delete_connection(db: Session, conn: EpicConnection) -> None:
    db.delete(conn)
    db.commit()
