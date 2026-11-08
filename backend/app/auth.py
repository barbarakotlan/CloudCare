"""Password hashing, login tokens, and the "who is calling?" dependency.

Two kinds of bearer tokens are accepted:

1. Our own HS256 tokens from `POST /auth/login` (demo accounts, offline fallback).
2. Supabase Auth access tokens (ES256, verified with the project's public JWKS).
   Enabled only when SUPABASE_URL is set.

Hackathon-grade: fine for a demo, not a full production auth system.
"""

import hashlib
import hmac
import logging
import os
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient, User
from app.outreach import guard
from app.outreach.phone import PhoneError, normalize_e164
from app.security import is_production

log = logging.getLogger("cloudcare.auth")

DEV_JWT_SECRET = "dev-only-change-me"
JWT_SECRET = os.getenv("JWT_SECRET") or DEV_JWT_SECRET
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = 12
# HS256 keys shorter than the hash output are brute-forceable offline from any issued token.
MIN_JWT_SECRET_LENGTH = 32


def jwt_secret_problem(secret: str | None = None) -> str | None:
    """Why the HS256 secret is unsafe for production, or None when it is fine."""
    secret = JWT_SECRET if secret is None else secret
    if not secret or secret == DEV_JWT_SECRET:
        return "JWT_SECRET is not set (development default in use)"
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        return f"JWT_SECRET is shorter than {MIN_JWT_SECRET_LENGTH} characters"
    return None


def local_tokens_enabled() -> bool:
    """CloudCare's own HS256 tokens (password login, phone-call tokens).

    Fail closed: in production (Render, or ENV=production) a missing or weak JWT_SECRET
    turns them off entirely, so a forged token signed with the public dev default can
    never be accepted. Supabase sign-in keeps working.
    """
    return not (is_production() and jwt_secret_problem() is not None)


if jwt_secret_problem() is not None:
    if is_production():
        log.error("%s; password sign-in and CloudCare tokens are disabled until it is fixed.", jwt_secret_problem())
    else:
        log.warning("%s. Fine for local development; set it before deploying.", jwt_secret_problem())

# ---- Supabase settings --------------------------------------------------------
# Project URL, e.g. https://<project-ref>.supabase.co. Unset = Supabase tokens are rejected.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else ""
SUPABASE_JWKS_URL = f"{SUPABASE_ISSUER}/.well-known/jwks.json" if SUPABASE_URL else ""
SUPABASE_AUDIENCE = "authenticated"
# Asymmetric only. The project signs with ES256; RS256 is the other key type Supabase offers.
# HS256 is deliberately absent so a Supabase-looking token can never be checked against a shared secret.
SUPABASE_ALGORITHMS = ["ES256", "RS256"]

VALID_ROLES = ("patient", "clinician")
PLACEHOLDER_PROCEDURE = "Pending clinician setup"


# ---- Passwords (stdlib scrypt, stored as "salt$hash") -----------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return hmac.compare_digest(check, digest)


# ---- Tokens -----------------------------------------------------------------

class LocalTokensDisabled(RuntimeError):
    """Production without a strong JWT_SECRET: CloudCare can't issue its own tokens."""


def sign_local_token(payload: dict) -> str:
    """Signs a CloudCare HS256 token. Every local token must carry `sub` and `exp`."""
    if not local_tokens_enabled():
        raise LocalTokensDisabled(jwt_secret_problem() or "local tokens disabled")
    if "sub" not in payload or "exp" not in payload:
        raise ValueError("local tokens need sub and exp")
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_HOURS),
    }
    return sign_local_token(payload)


class TokenError(Exception):
    """A bearer token could not be accepted. `detail` is safe to show to the client."""

    def __init__(self, detail: str = "Not logged in", status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """One shared JWKS client so signing keys are fetched once and cached.

    Supabase caches the JWKS at its edge for 10 minutes and asks clients not to
    cache much longer than that, so the key set is kept for 5 minutes here.
    (cache_keys=True would pin keys by kid until restart, so a revoked key would
    keep working; the expiring key-set cache avoids that.)
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(SUPABASE_JWKS_URL, cache_jwk_set=True, lifespan=300, timeout=5)
    return _jwks_client


def _decode_local(token: str) -> dict:
    if not local_tokens_enabled():
        raise TokenError()
    try:
        payload = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.ExpiredSignatureError:
        raise TokenError("Session expired, please log in again")
    except jwt.PyJWTError:
        raise TokenError()
    if "sub" not in payload:
        raise TokenError()
    claims = {"provider": "local", "sub": payload["sub"], "role": payload.get("role")}
    if "purpose" in payload:
        claims["purpose"] = payload["purpose"]
    return claims


# A phone-call token (outreach/calls.py) is handed to the voice provider for one call, so it
# only opens what the agent's tool needs: Foggy's chat. Everything else answers 401.
PHONE_CALL_PATHS = ("/chat",)


def _purpose_allows(purpose: object, path: str) -> bool:
    if purpose is None:
        return True
    if purpose == "phone_call":
        return any(path == p or path.startswith(p + "/") for p in PHONE_CALL_PATHS)
    return False


def _decode_supabase(token: str) -> dict:
    if not SUPABASE_URL:
        log.warning("Received a Supabase-style token but SUPABASE_URL is not set on the API.")
        raise TokenError("Supabase sign-in is not enabled on this API (SUPABASE_URL is not set)")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as exc:
        log.error("Could not fetch Supabase signing keys from %s: %s", SUPABASE_JWKS_URL, exc)
        raise TokenError(
            "Could not load Supabase signing keys; check SUPABASE_URL on the API",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except jwt.PyJWKClientError as exc:
        # Usually an unknown `kid`: token from another project, or the key was rotated away.
        log.warning("Supabase token signing key not found in %s: %s", SUPABASE_JWKS_URL, exc)
        raise TokenError("Supabase token was not signed by this project's keys")
    except jwt.PyJWTError:
        raise TokenError()

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=SUPABASE_ALGORITHMS,
            audience=SUPABASE_AUDIENCE,
            issuer=SUPABASE_ISSUER,
            leeway=10,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenError("Session expired, please log in again")
    except jwt.InvalidAudienceError:
        raise TokenError("Supabase token has the wrong audience")
    except jwt.InvalidIssuerError:
        log.warning("Supabase token issuer mismatch; expected %s", SUPABASE_ISSUER)
        raise TokenError("Supabase token was issued by a different project")
    except jwt.PyJWTError as exc:
        # Exception type only: PyJWT messages never include the token, but keep logs minimal.
        log.info("Rejected Supabase token: %s", type(exc).__name__)
        raise TokenError()

    if claims.get("is_anonymous"):
        raise TokenError("Anonymous Supabase sessions cannot use this API")

    # Authorization data comes from app_metadata only: only the service role can write it.
    # user_metadata is editable by the user, so it is used for the display name and nothing else.
    app_metadata = claims.get("app_metadata") or {}
    user_metadata = claims.get("user_metadata") or {}
    role = app_metadata.get("role") if isinstance(app_metadata, dict) else None
    full_name = user_metadata.get("full_name") if isinstance(user_metadata, dict) else None
    phone = user_metadata.get("phone") if isinstance(user_metadata, dict) else None
    email = claims.get("email")
    return {
        "provider": "supabase",
        "sub": claims["sub"],
        "email": email.strip().lower() if isinstance(email, str) and email.strip() else None,
        "role": role if role in VALID_ROLES else None,
        "full_name": full_name.strip() if isinstance(full_name, str) and full_name.strip() else None,
        # The mobile number typed at sign-up. Contact info only, never used for authorization.
        "phone": phone if isinstance(phone, str) else None,
    }


def decode_token(token: str) -> dict:
    """Verifies a bearer token and returns normalized claims.

    Returns {"provider": "local"|"supabase", "sub", "role", ...}; Supabase tokens
    also carry "email" and "full_name". Raises TokenError when the token is not acceptable.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise TokenError()
    # The header only routes the token to a verifier; each verifier pins its own algorithms.
    if header.get("alg") == JWT_ALGORITHM:
        return _decode_local(token)
    return _decode_supabase(token)


# ---- Supabase users -> local users rows ---------------------------------------

def _signup_phone(raw: str | None) -> str | None:
    """The sign-up mobile number in E.164, or None if missing or unusable (never blocks sign-in)."""
    if not raw:
        return None
    try:
        return normalize_e164(raw)
    except PhoneError:
        log.info("Ignoring a sign-up phone number that isn't a usable mobile number.")
        return None


def _ensure_patient_profile(db: Session, user: User, phone: str | None = None) -> None:
    """Gives a new patient a placeholder profile so /patients/me works on first login.

    The profile starts with no clinician: a self sign-up stays out of every clinician's
    worklist until a clinician claims it (GET /patients/unassigned, POST /patients/{id}/assign).
    """
    if db.scalar(select(Patient.id).where(Patient.user_id == user.id)) is not None:
        return
    patient = Patient(
        user_id=user.id,
        clinician_id=None,
        procedure_name=PLACEHOLDER_PROCEDURE,
        procedure_type="unknown",
        surgery_date=date.today(),
        comorbidities=[],
        phone=_signup_phone(phone),
    )
    db.add(patient)
    if patient.phone:
        # A number typed at sign-up is a new destination like any other (outreach/guard.py).
        db.flush()
        guard.note_phone_change(patient.id)


def _user_from_supabase(db: Session, claims: dict) -> User:
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError:
        raise TokenError()

    user = db.get(User, user_id)
    if user is not None:
        return user

    email = claims.get("email")
    if not email:
        raise TokenError("This Supabase account has no email address")

    # Accounts that existed locally before Supabase (e.g. demo rows created on SQLite)
    # keep their own ids; match them by email instead.
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        if user.id != user_id:
            # Ids only: email addresses are personal data and stay out of the logs.
            log.info("Supabase user %s matched local user %s by email.", user_id, user.id)
        return user

    user = User(
        id=user_id,
        email=email,
        full_name=claims.get("full_name") or email,
        role=claims.get("role") or "patient",
        # Not a usable scrypt hash, so POST /auth/login can never succeed for this row.
        password_hash="supabase",
    )
    db.add(user)
    try:
        db.flush()
        if user.role == "patient":
            _ensure_patient_profile(db, user, claims.get("phone"))
        db.commit()
    except IntegrityError:
        # Two first requests raced to create the same user; use the winner's row.
        db.rollback()
        user = db.get(User, user_id) or db.scalar(select(User).where(User.email == email))
        if user is None:
            raise
        return user
    log.info("Created local %s account for Supabase user %s.", user.role, user_id)
    return user


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Use in a route as `user: User = Depends(get_current_user)`."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    try:
        claims = decode_token(creds.credentials)
        if not _purpose_allows(claims.get("purpose"), request.url.path):
            raise TokenError()
        if claims["provider"] == "supabase":
            user = _user_from_supabase(db, claims)
        else:
            user = db.get(User, uuid.UUID(claims["sub"]))
    except TokenError as exc:
        raise HTTPException(exc.status_code, exc.detail)
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


# ---- Role checks ------------------------------------------------------------

def require_clinician(user: User = Depends(get_current_user)) -> User:
    if user.role != "clinician":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Clinicians only")
    return user


def get_current_patient(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Patient:
    """The Patient profile of the logged-in patient user."""
    if user.role != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Patients only")
    patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No patient profile for this account")
    return patient


def get_patient_for_clinician(db: Session, clinician: User, patient_id: uuid.UUID) -> Patient:
    """Loads a patient, making sure they are assigned to this clinician."""
    patient = db.get(Patient, patient_id)
    if patient is None or patient.clinician_id != clinician.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return patient
