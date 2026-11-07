"""Password hashing, login tokens, and the "who is calling?" dependency.

Hackathon-grade: fine for a demo, not a full production auth system.
"""

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient, User

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = 12


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

def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Use in a route as `user: User = Depends(get_current_user)`."""
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    if user is None:
        raise unauthorized
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
