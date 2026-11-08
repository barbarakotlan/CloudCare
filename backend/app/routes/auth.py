import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import LocalTokensDisabled, create_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.security import RateLimiter, client_ip, too_many

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed sign-ins: per (address, email) to stop password guessing on one account without
# letting a stranger lock that account for everyone, plus per address across all emails.
LOGIN_FAILURES = RateLimiter("login-failures", limit=10, window=15 * 60)
LOGIN_ATTEMPTS = RateLimiter("login-attempts", limit=60, window=15 * 60)

# Compared against when the email is unknown, so both paths cost one scrypt (no timing oracle).
_DUMMY_HASH = hash_password("not-a-real-password")


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str  # 'patient' | 'clinician' -> frontend picks the dashboard


class LoginResponse(BaseModel):
    access_token: str
    user: UserOut


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    ip = client_ip(request)
    failure_key = f"{ip}|{email}"

    wait = LOGIN_ATTEMPTS.hit(ip) or LOGIN_FAILURES.blocked(failure_key)
    if wait:
        raise too_many("Too many sign-in attempts.", wait)

    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(body.password, user.password_hash if user is not None else _DUMMY_HASH)
    if user is None or not ok:
        LOGIN_FAILURES.hit(failure_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    try:
        token = create_token(user)
    except LocalTokensDisabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Password sign-in is turned off on this server. Use the main sign-in."
        )
    LOGIN_FAILURES.clear(failure_key)
    return LoginResponse(
        access_token=token,
        user=UserOut(id=user.id, full_name=user.full_name, role=user.role),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """Returns whoever owns the token. Handy for testing and page reloads."""
    return UserOut(id=user.id, full_name=user.full_name, role=user.role)
