"""Epic SMART on FHIR connect flow tests (no network, no Epic client id needed).

Epic is replaced by an httpx.MockTransport; the database is in-memory SQLite.

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_epic_oauth.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import base64
import hashlib
import io
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
import jwt  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.epic import config as epic_config  # noqa: E402
from app.epic import crypto, oauth, store  # noqa: E402
from app.models import EpicConnection, EpicOAuthState, User  # noqa: E402

BASE = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
AUTHORIZE = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"
TOKEN = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
REDIRECT = "http://localhost:3000/api/auth/callback/epic"
CLIENT_ID = "test-non-production-client-id"
KEY = Fernet.generate_key().decode()

EPIC_ENV = (
    "EPIC_CLIENT_ID", "EPIC_CLIENT_SECRET", "EPIC_FHIR_BASE_URL", "EPIC_STU3_BASE_URL", "EPIC_REDIRECT_URI",
    "EPIC_SCOPES", "EPIC_TOKEN_ENCRYPTION_KEY", "EPIC_SANDBOX", "EPIC_LABS_FHIR_VERSION",
)


def configure(**overrides) -> None:
    for name in EPIC_ENV:
        os.environ.pop(name, None)
    values = {
        "EPIC_CLIENT_ID": CLIENT_ID,
        "EPIC_TOKEN_ENCRYPTION_KEY": KEY,
        "EPIC_FHIR_BASE_URL": BASE,
        "EPIC_REDIRECT_URI": REDIRECT,
    }
    values.update(overrides)
    for name, value in values.items():
        if value is not None:
            os.environ[name] = value


class FakeEpic:
    """Just enough of Epic's OAuth server: discovery + token endpoint."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.token_replies: list[tuple[int, dict]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == f"{BASE}/.well-known/smart-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": AUTHORIZE,
                    "token_endpoint": TOKEN,
                    "code_challenge_methods_supported": ["S256"],
                },
            )
        if url == TOKEN:
            status, body = self.token_replies.pop(0) if self.token_replies else (400, {"error": "invalid_grant"})
            return httpx.Response(status, json=body)
        return httpx.Response(404, json={"resourceType": "OperationOutcome"})

    def token_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if str(r.url) == TOKEN]


def install_fake() -> FakeEpic:
    fake = FakeEpic()
    epic_config.set_transport(httpx.MockTransport(fake.handler))
    return fake


def token_reply(**overrides) -> dict:
    id_token = jwt.encode({"sub": "mychart-user-1", "fhirUser": f"{BASE}/Patient/erXuFYUfucBZaryVksYEcMg3"}, "x" * 32)
    body = {
        "access_token": "ACCESS-abc123",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid fhirUser patient/MedicationRequest.read patient/Observation.read",
        "patient": "erXuFYUfucBZaryVksYEcMg3",
        "id_token": id_token,
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not None}


def make_app():
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
    client = TestClient(app)
    with TestSession() as db:
        users = {
            "a": User(email="a@example.com", full_name="Pat A", role="patient", password_hash="x"),
            "b": User(email="b@example.com", full_name="Pat B", role="patient", password_hash="x"),
            "doc": User(email="doc@example.com", full_name="Dr. Doc", role="clinician", password_hash="x"),
        }
        db.add_all(users.values())
        db.commit()
        headers = {k: {"Authorization": f"Bearer {auth.create_token(u)}"} for k, u in users.items()}
        ids = {k: u.id for k, u in users.items()}
    return client, TestSession, headers, ids


def start(client, headers) -> dict:
    res = client.post("/epic/connect/start", headers=headers)
    assert res.status_code == 200, res.text
    url = urlsplit(res.json()["authorize_url"])
    return {k: v[0] for k, v in parse_qs(url.query).items()} | {"_endpoint": f"{url.scheme}://{url.netloc}{url.path}"}


# ---- PKCE / authorize URL ------------------------------------------------------------------


def test_pkce_matches_rfc7636_example():
    # RFC 7636 appendix B.
    assert oauth.code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    verifier = oauth.new_code_verifier()
    assert 43 <= len(verifier) <= 128


def test_authorize_url_contents():
    configure()
    install_fake()
    client, TestSession, headers, ids = make_app()
    q = start(client, headers["a"])

    assert q["_endpoint"] == AUTHORIZE  # from discovery, not hardcoded
    assert q["response_type"] == "code"
    assert q["client_id"] == CLIENT_ID
    assert q["redirect_uri"] == REDIRECT
    assert q["aud"] == BASE
    assert q["code_challenge_method"] == "S256"
    assert set(q["scope"].split()) >= {"openid", "fhirUser", "patient/MedicationRequest.read", "patient/DocumentReference.read"}
    assert "offline_access" not in q["scope"].split()
    assert len(q["state"]) >= 32

    with TestSession() as db:
        row = db.get(EpicOAuthState, q["state"])
        assert row is not None and row.user_id == ids["a"]
        verifier = crypto.decrypt(row.code_verifier, KEY)
        assert row.code_verifier != verifier  # stored encrypted
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        assert q["code_challenge"] == expected
        ttl = oauth.as_utc(row.expires_at) - oauth.utcnow()
        assert timedelta(minutes=9) < ttl <= timedelta(minutes=10)


def test_start_needs_a_patient():
    configure()
    install_fake()
    client, _, headers, _ = make_app()
    assert client.post("/epic/connect/start").status_code == 401
    res = client.post("/epic/connect/start", headers=headers["doc"])
    assert res.status_code == 403


def test_new_start_replaces_previous_state():
    configure()
    install_fake()
    client, TestSession, headers, ids = make_app()
    first = start(client, headers["a"])["state"]
    second = start(client, headers["a"])["state"]
    with TestSession() as db:
        states = db.scalars(select(EpicOAuthState.state).where(EpicOAuthState.user_id == ids["a"])).all()
    assert states == [second] and first != second


# ---- not configured --------------------------------------------------------------------------


def test_missing_client_id_returns_503():
    configure(EPIC_CLIENT_ID=None)
    install_fake()
    client, _, headers, _ = make_app()
    for method, path in (("post", "/epic/connect/start"), ("get", "/epic/status"), ("get", "/epic/records"),
                         ("delete", "/epic/connection")):
        res = getattr(client, method)(path, headers=headers["a"])
        assert res.status_code == 503, (path, res.status_code)
        assert "isn't configured" in res.json()["detail"]
    res = client.post("/epic/connect/callback", json={"code": "c", "state": "s"})
    assert res.status_code == 503


def test_missing_or_bad_encryption_key_returns_503():
    install_fake()
    client, _, headers, _ = make_app()
    configure(EPIC_TOKEN_ENCRYPTION_KEY=None)
    assert client.get("/epic/status", headers=headers["a"]).status_code == 503
    configure(EPIC_TOKEN_ENCRYPTION_KEY="not-a-fernet-key")
    assert client.get("/epic/status", headers=headers["a"]).status_code == 503
    configure()
    assert client.get("/epic/status", headers=headers["a"]).status_code == 200


# ---- state validation ----------------------------------------------------------------------------


def test_unknown_state_is_rejected_without_calling_epic():
    configure()
    fake = install_fake()
    client, _, _, _ = make_app()
    res = client.post("/epic/connect/callback", json={"code": "code-1", "state": "never-issued"})
    assert res.status_code == 400 and res.json()["detail"] == "invalid_state"
    assert fake.token_requests() == []


def test_expired_state_is_rejected_and_removed():
    configure()
    fake = install_fake()
    client, TestSession, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    with TestSession() as db:
        row = db.get(EpicOAuthState, state)
        row.expires_at = oauth.utcnow() - timedelta(seconds=1)
        db.commit()
    res = client.post("/epic/connect/callback", json={"code": "code-1", "state": state})
    assert res.status_code == 400 and res.json()["detail"] == "expired_state"
    assert fake.token_requests() == []
    with TestSession() as db:
        assert db.get(EpicOAuthState, state) is None


def test_state_is_single_use():
    configure()
    fake = install_fake()
    fake.token_replies = [(200, token_reply()), (200, token_reply())]
    client, _, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    first = client.post("/epic/connect/callback", json={"code": "code-1", "state": state})
    assert first.status_code == 200, first.text
    again = client.post("/epic/connect/callback", json={"code": "code-1", "state": state})
    assert again.status_code == 400 and again.json()["detail"] == "invalid_state"
    assert len(fake.token_requests()) == 1


def test_iss_mismatch_is_rejected():
    configure()
    fake = install_fake()
    client, _, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    res = client.post(
        "/epic/connect/callback",
        json={"code": "code-1", "state": state, "iss": "https://evil.example.com/api/FHIR/R4"},
    )
    assert res.status_code == 400 and res.json()["detail"] == "iss_mismatch"
    assert fake.token_requests() == []


def test_base_url_changed_between_start_and_callback_is_rejected():
    configure()
    install_fake()
    client, _, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    configure(EPIC_FHIR_BASE_URL="https://other.example.org/api/FHIR/R4")
    res = client.post("/epic/connect/callback", json={"code": "code-1", "state": state})
    assert res.status_code == 400 and res.json()["detail"] == "iss_mismatch"


# ---- code exchange -------------------------------------------------------------------------------------


def test_successful_exchange_stores_encrypted_tokens():
    configure()
    fake = install_fake()
    fake.token_replies = [(200, token_reply())]
    client, TestSession, headers, ids = make_app()
    state = start(client, headers["a"])["state"]
    with TestSession() as db:
        verifier = crypto.decrypt(db.get(EpicOAuthState, state).code_verifier, KEY)

    res = client.post("/epic/connect/callback", json={"code": "code-1", "state": state})
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True, "patient_fhir_id": "erXuFYUfucBZaryVksYEcMg3"}

    # Public client: client_id in the body, PKCE verifier, no Authorization header.
    (req,) = fake.token_requests()
    form = {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
    assert form == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "redirect_uri": REDIRECT,
        "code_verifier": verifier,
        "client_id": CLIENT_ID,
    }
    assert "authorization" not in req.headers

    with TestSession() as db:
        conn = db.scalar(select(EpicConnection).where(EpicConnection.user_id == ids["a"]))
        assert conn is not None and conn.status == "active"
        assert conn.iss == BASE
        assert conn.patient_fhir_id == "erXuFYUfucBZaryVksYEcMg3"
        assert "ACCESS-abc123" not in conn.access_token_enc
        assert store.access_token(conn, store_settings()) == "ACCESS-abc123"
        assert conn.refresh_token_enc is None
        assert conn.id_token_sub == f"{BASE}/Patient/erXuFYUfucBZaryVksYEcMg3"
        assert "patient/MedicationRequest.read" in conn.scope
        assert oauth.as_utc(conn.expires_at) > oauth.utcnow() + timedelta(minutes=55)
        assert db.scalars(select(EpicOAuthState)).all() == []

    status = client.get("/epic/status", headers=headers["a"]).json()
    assert status["connected"] is True and status["revoked"] is False
    assert status["issuer"] == BASE and status["sandbox"] is True
    assert "openid" in status["scopes"]


def store_settings():
    return epic_config.get_settings()


def test_confidential_client_uses_basic_auth_and_keeps_refresh_token():
    configure(EPIC_CLIENT_SECRET="s3cret")
    fake = install_fake()
    fake.token_replies = [(200, token_reply(refresh_token="REFRESH-xyz"))]
    client, TestSession, headers, ids = make_app()
    state = start(client, headers["a"])["state"]
    assert client.post("/epic/connect/callback", json={"code": "c", "state": state}).status_code == 200

    (req,) = fake.token_requests()
    expected = "Basic " + base64.b64encode(f"{CLIENT_ID}:s3cret".encode()).decode()
    assert req.headers["authorization"] == expected
    assert "client_id" not in parse_qs(req.content.decode())
    with TestSession() as db:
        conn = db.scalar(select(EpicConnection).where(EpicConnection.user_id == ids["a"]))
        assert "REFRESH-xyz" not in (conn.refresh_token_enc or "")
        assert store.refresh_token(conn, store_settings()) == "REFRESH-xyz"


def test_token_without_patient_is_rejected():
    configure()
    fake = install_fake()
    fake.token_replies = [(200, token_reply(patient=None))]
    client, TestSession, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    res = client.post("/epic/connect/callback", json={"code": "c", "state": state})
    assert res.status_code == 400 and res.json()["detail"] == "no_patient"
    with TestSession() as db:
        assert db.scalars(select(EpicConnection)).all() == []


def test_token_with_user_scopes_is_rejected():
    configure()
    fake = install_fake()
    fake.token_replies = [(200, token_reply(scope="openid user/Patient.read"))]
    client, _, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    res = client.post("/epic/connect/callback", json={"code": "c", "state": state})
    assert res.status_code == 400 and res.json()["detail"] == "unexpected_scope"


def test_token_endpoint_error_is_reported_generically():
    configure()
    fake = install_fake()
    fake.token_replies = [(400, {"error": "invalid_grant", "error_description": "code expired"})]
    client, _, headers, _ = make_app()
    state = start(client, headers["a"])["state"]
    res = client.post("/epic/connect/callback", json={"code": "c", "state": state})
    assert res.status_code == 400 and res.json()["detail"] == "token_exchange_failed"


def test_reconnect_replaces_the_existing_row():
    configure()
    fake = install_fake()
    fake.token_replies = [(200, token_reply()), (200, token_reply(access_token="ACCESS-second"))]
    client, TestSession, headers, ids = make_app()
    for _ in range(2):
        state = start(client, headers["a"])["state"]
        assert client.post("/epic/connect/callback", json={"code": "c", "state": state}).status_code == 200
    with TestSession() as db:
        rows = db.scalars(select(EpicConnection).where(EpicConnection.user_id == ids["a"])).all()
        assert len(rows) == 1 and store.access_token(rows[0], store_settings()) == "ACCESS-second"


def test_logs_never_contain_tokens_codes_or_ids():
    configure(EPIC_CLIENT_SECRET="s3cret")
    fake = install_fake()
    fake.token_replies = [(200, token_reply(refresh_token="REFRESH-xyz"))]
    client, TestSession, headers, _ = make_app()

    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    logger = logging.getLogger("cloudcare.epic")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        state = start(client, headers["a"])["state"]
        client.post("/epic/connect/callback", json={"code": "SECRET-CODE", "state": state})
        client.post("/epic/connect/callback", json={"code": "SECRET-CODE", "state": state})
    finally:
        logger.removeHandler(handler)
    text = buffer.getvalue()
    assert "epic.connect.callback.ok" in text
    for secret in ("ACCESS-abc123", "REFRESH-xyz", "SECRET-CODE", "erXuFYUfucBZaryVksYEcMg3", state, "s3cret"):
        assert secret not in text, secret


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
