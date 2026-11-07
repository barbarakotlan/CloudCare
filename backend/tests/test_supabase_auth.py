"""Supabase token verification tests (no network, no Supabase project needed).

A throwaway ES256 key pair stands in for the project's JWKS.

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_supabase_auth.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import sys
import time
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.models import Patient, User  # noqa: E402

PROJECT_URL = "https://example-ref.supabase.co"
ISSUER = f"{PROJECT_URL}/auth/v1"
KID = "test-key-1"

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKSClient:
    """Mimics PyJWKClient.get_signing_key_from_jwt for a single known kid."""

    def get_signing_key_from_jwt(self, token: str):
        if jwt.get_unverified_header(token).get("kid") != KID:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return _FakeSigningKey(PRIVATE_KEY.public_key())


def _configure_supabase(enabled: bool = True) -> None:
    auth.SUPABASE_URL = PROJECT_URL if enabled else ""
    auth.SUPABASE_ISSUER = ISSUER if enabled else ""
    auth.SUPABASE_JWKS_URL = f"{ISSUER}/.well-known/jwks.json" if enabled else ""
    auth._get_jwks_client = lambda: _FakeJWKSClient()


def _supabase_token(key=PRIVATE_KEY, kid=KID, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": "authenticated",
        "sub": str(uuid.uuid4()),
        "role": "authenticated",
        "email": "new.patient@example.com",
        "app_metadata": {"provider": "email"},
        "user_metadata": {"full_name": "Casey Rivera"},
        "is_anonymous": False,
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})


def _expect_rejected(token: str, contains: str = "") -> auth.TokenError:
    try:
        auth.decode_token(token)
    except auth.TokenError as exc:
        assert contains.lower() in exc.detail.lower(), exc.detail
        return exc
    raise AssertionError("token was accepted but should have been rejected")


# ---- decode_token -------------------------------------------------------------

def test_valid_supabase_token_is_accepted():
    _configure_supabase()
    sub = str(uuid.uuid4())
    claims = auth.decode_token(
        _supabase_token(sub=sub, email="Casey@Example.com", app_metadata={"role": "clinician"})
    )
    assert claims["provider"] == "supabase"
    assert claims["sub"] == sub
    assert claims["email"] == "casey@example.com"
    assert claims["role"] == "clinician"
    assert claims["full_name"] == "Casey Rivera"


def test_wrong_audience_is_rejected():
    _configure_supabase()
    _expect_rejected(_supabase_token(aud="anon"), "audience")


def test_wrong_issuer_is_rejected():
    _configure_supabase()
    _expect_rejected(_supabase_token(iss="https://other-ref.supabase.co/auth/v1"), "different project")


def test_expired_token_is_rejected():
    _configure_supabase()
    _expect_rejected(_supabase_token(exp=int(time.time()) - 3600), "expired")


def test_token_signed_by_another_key_is_rejected():
    _configure_supabase()
    _expect_rejected(_supabase_token(key=OTHER_PRIVATE_KEY))


def test_unknown_kid_is_rejected():
    _configure_supabase()
    _expect_rejected(_supabase_token(kid="rotated-away"), "signed by this project")


def test_anonymous_session_is_rejected():
    _configure_supabase()
    _expect_rejected(_supabase_token(is_anonymous=True), "anonymous")


def test_role_ignores_user_metadata():
    _configure_supabase()
    claims = auth.decode_token(
        _supabase_token(app_metadata={"provider": "email"}, user_metadata={"role": "clinician", "full_name": "X"})
    )
    assert claims["role"] is None  # falls back to patient when the user row is created


def test_supabase_token_rejected_when_not_configured():
    _configure_supabase(enabled=False)
    try:
        _expect_rejected(_supabase_token(), "SUPABASE_URL")
    finally:
        _configure_supabase()


def test_local_hs256_token_still_works():
    _configure_supabase()
    user = User(id=uuid.uuid4(), email="a@b.c", full_name="A", role="patient", password_hash="x")
    claims = auth.decode_token(auth.create_token(user))
    assert claims == {"provider": "local", "sub": str(user.id), "role": "patient"}


def test_hs256_token_with_wrong_secret_is_rejected():
    _configure_supabase()
    forged = jwt.encode({"sub": str(uuid.uuid4()), "exp": int(time.time()) + 60}, "not-the-secret", algorithm="HS256")
    _expect_rejected(forged)


# ---- full request path (in-memory SQLite) --------------------------------------

def _test_client():
    from app.main import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with` block: skips the startup seed so this test owns the database.
    return TestClient(app), TestSession


def test_first_supabase_login_creates_patient_with_placeholder_profile():
    _configure_supabase()
    client, TestSession = _test_client()
    with TestSession() as db:
        clinician = User(email="doc@example.com", full_name="Dr. Doc", role="clinician", password_hash="x")
        db.add(clinician)
        db.commit()
        clinician_id = clinician.id

    sub = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {_supabase_token(sub=sub)}"}

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json() == {"id": sub, "full_name": "Casey Rivera", "role": "patient"}

    profile = client.get("/patients/me", headers=headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["procedure_name"] == auth.PLACEHOLDER_PROCEDURE

    # Second request reuses the same rows.
    assert client.get("/auth/me", headers=headers).status_code == 200
    with TestSession() as db:
        assert len(db.scalars(select(User).where(User.email == "new.patient@example.com")).all()) == 1
        patient = db.scalar(select(Patient).where(Patient.user_id == uuid.UUID(sub)))
        assert patient is not None and patient.clinician_id == clinician_id


def test_supabase_clinician_role_from_app_metadata():
    _configure_supabase()
    client, _ = _test_client()
    token = _supabase_token(email="newdoc@example.com", app_metadata={"role": "clinician"})
    res = client.get("/escalations", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text


def test_existing_local_user_is_matched_by_email():
    _configure_supabase()
    client, TestSession = _test_client()
    with TestSession() as db:
        local = User(email="patient@demo.com", full_name="Jordan Lee", role="patient", password_hash="x")
        db.add(local)
        db.commit()
        local_id = str(local.id)
    token = _supabase_token(email="patient@demo.com", user_metadata={})
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["id"] == local_id


def test_bad_supabase_token_returns_401_with_detail():
    _configure_supabase()
    client, _ = _test_client()
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {_supabase_token(aud='anon')}"})
    assert res.status_code == 401
    assert "audience" in res.json()["detail"]


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
