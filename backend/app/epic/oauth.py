"""SMART on FHIR standalone launch against Epic: PKCE, authorize URL, token calls.

Epic facts this relies on (checked against fhir.epic.com, see docs/epic-mychart.md):
- Only the S256 code_challenge_method is supported.
- `aud` is the FHIR base URL of the resource server; Epic requires it since May 2023.
- Non-confidential clients send client_id in the token request body and get no
  refresh token. Confidential clients authenticate with HTTP Basic
  (client_id:client_secret) and can be set up to receive refresh tokens.
- The token response carries `patient` (the patient's FHIR id) for patient-facing
  launches, plus `scope`, `expires_in`, and `id_token` when `openid` was requested.
"""

import base64
import hashlib
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt

from app.epic.config import EpicSettings, EpicUnavailable, http_client

log = logging.getLogger("cloudcare.epic")

STATE_TTL = timedelta(minutes=10)
# FHIR resource ids: [A-Za-z0-9\-\.]{1,64}. Checked before we ever put one in a URL.
FHIR_ID_RE = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands datetimes back without tzinfo; they were written as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ---- PKCE + state -----------------------------------------------------------------


def new_code_verifier() -> str:
    # 64 random bytes -> 86 url-safe characters, inside RFC 7636's 43..128 range.
    return secrets.token_urlsafe(64)


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorize_url(authorization_endpoint: str, settings: EpicSettings, state: str, verifier: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri,
        "scope": settings.scopes,
        "state": state,
        "aud": settings.fhir_base_url,
        "code_challenge": code_challenge(verifier),
        "code_challenge_method": "S256",
    }
    sep = "&" if "?" in authorization_endpoint else "?"
    return f"{authorization_endpoint}{sep}{urlencode(params)}"


# ---- Token endpoint ----------------------------------------------------------------


class EpicOAuthError(Exception):
    """Token endpoint said no. `code` is a short, log-safe reason."""

    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class TokenSet:
    access_token: str
    token_type: str
    expires_at: datetime | None
    scope: str
    patient: str | None
    refresh_token: str | None = None
    id_token_sub: str | None = None


def _id_token_subject(id_token: str | None) -> str | None:
    """`sub` (or fhirUser) from the id_token, used only as an informational label.

    The id_token comes straight from Epic's token endpoint over TLS, which OIDC
    Core 3.1.3.7 accepts in place of a signature check for this flow. Nothing in
    CloudCare authorizes anything based on it.
    """
    if not id_token:
        return None
    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return None
    value = claims.get("fhirUser") or claims.get("sub")
    return str(value)[:255] if value else None


def parse_token_response(data: dict, *, require_patient: bool) -> TokenSet:
    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise EpicOAuthError("no_access_token")
    token_type = str(data.get("token_type") or "")
    if token_type.lower() != "bearer":
        raise EpicOAuthError("unexpected_token_type")

    patient = data.get("patient")
    if patient is not None and (not isinstance(patient, str) or not FHIR_ID_RE.match(patient)):
        raise EpicOAuthError("invalid_patient")
    if require_patient and not patient:
        # Patient-facing launches always carry the patient's FHIR id. Without it
        # the app was registered for the wrong audience.
        raise EpicOAuthError("no_patient")

    scope = " ".join(str(data.get("scope") or "").split())
    # We only ever ask for patient-level access. A token that grants user/ or
    # system/ scopes means the registration is not what we expect.
    if any(s.startswith(("user/", "system/")) for s in scope.split()):
        raise EpicOAuthError("unexpected_scope")

    expires_at = None
    try:
        expires_in = int(data.get("expires_in"))
        expires_at = utcnow() + timedelta(seconds=max(0, expires_in))
    except (TypeError, ValueError):
        pass

    refresh_token = data.get("refresh_token")
    return TokenSet(
        access_token=access_token,
        token_type="Bearer",
        expires_at=expires_at,
        scope=scope,
        patient=patient,
        refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else None,
        id_token_sub=_id_token_subject(data.get("id_token")),
    )


def _client_auth(settings: EpicSettings, form: dict) -> tuple[dict, httpx.BasicAuth | None]:
    if settings.confidential:
        return form, httpx.BasicAuth(settings.client_id, settings.client_secret)
    return {**form, "client_id": settings.client_id}, None


def _post_token(token_endpoint: str, settings: EpicSettings, form: dict, event: str) -> dict:
    form, auth = _client_auth(settings, form)
    try:
        with http_client() as client:
            res = client.post(
                token_endpoint,
                data=form,
                auth=auth,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        log.warning("%s.network_error type=%s", event, type(exc).__name__)
        raise EpicUnavailable("Couldn't reach Epic's token endpoint") from exc

    if res.status_code >= 500:
        log.warning("%s.failed status=%s", event, res.status_code)
        raise EpicUnavailable("Epic's token endpoint is unavailable")
    try:
        data = res.json()
    except ValueError:
        data = {}
    if res.status_code != 200:
        # OAuth error codes (invalid_grant, invalid_client, ...) are safe to log;
        # error_description is not logged because it can echo request values.
        err = data.get("error") if isinstance(data, dict) else None
        code = err if isinstance(err, str) and re.fullmatch(r"[a-z_]{1,40}", err) else "token_error"
        log.warning("%s.rejected status=%s error=%s", event, res.status_code, code)
        raise EpicOAuthError(code, res.status_code)
    if not isinstance(data, dict):
        raise EpicOAuthError("malformed_token_response")
    log.info("%s.ok status=%s", event, res.status_code)
    return data


def exchange_code(token_endpoint: str, settings: EpicSettings, code: str, verifier: str) -> TokenSet:
    data = _post_token(
        token_endpoint,
        settings,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.redirect_uri,
            "code_verifier": verifier,
        },
        "epic.token.exchange",
    )
    return parse_token_response(data, require_patient=True)


def refresh_tokens(token_endpoint: str, settings: EpicSettings, refresh_token: str) -> TokenSet:
    data = _post_token(
        token_endpoint,
        settings,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
        "epic.token.refresh",
    )
    return parse_token_response(data, require_patient=False)


def revoke_token(revocation_endpoint: str, settings: EpicSettings, token: str, hint: str) -> None:
    """Best effort (RFC 7009). Epic's sandbox does not advertise a revocation endpoint."""
    form, auth = _client_auth(settings, {"token": token, "token_type_hint": hint})
    try:
        with http_client() as client:
            res = client.post(revocation_endpoint, data=form, auth=auth)
        log.info("epic.token.revoke status=%s", res.status_code)
    except httpx.HTTPError as exc:
        log.info("epic.token.revoke.network_error type=%s", type(exc).__name__)
