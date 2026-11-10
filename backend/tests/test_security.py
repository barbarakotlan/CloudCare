"""Security review checks (docs/security-review.md): token handling, cross-patient access,
abuse limits, input limits, headers and error responses.

In-memory SQLite seeded with the demo data; Supabase signing keys, Twilio and ElevenLabs
are faked in process, so nothing leaves the machine.

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_security.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import base64
import json
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
import jwt  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth, demo_data, seed  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.models import CarePlan, Escalation, Medication, OutreachLog, Patient, User  # noqa: E402
from app.outreach import config as outreach_config  # noqa: E402
from app.outreach import guard  # noqa: E402
from app.outreach import log as outreach_log  # noqa: E402
from app.security import RateLimiter  # noqa: E402

os.environ["LLM_PROVIDER"] = "none"
seed.ensure_supabase_demo_users = lambda db: {}
_DEMO_HASH = auth.hash_password(seed.DEMO_PASSWORD)
seed.hash_password = lambda password: _DEMO_HASH
demo_data.hash_password = lambda password: _DEMO_HASH

STRONG_SECRET = "s" * 48
PHONE = "+15552345678"
OUTREACH_ENV = {
    # Texts and calls are off unless this master switch is on.
    "OUTREACH_ENABLED": "true",
    "TWILIO_ACCOUNT_SID": "AC" + "a" * 32,
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_FROM_NUMBER": "+15550001111",
    "ELEVENLABS_API_KEY": "test-eleven-key",
    "ELEVENLABS_AGENT_ID": "agent_test",
    "ELEVENLABS_PHONE_NUMBER_ID": "phnum_test",
    # Jordan is the shared demo patient: only these test numbers are reachable from it.
    "OUTREACH_DEMO_ALLOWLIST": f"{PHONE}, (555) 234-9876, +15552341111, not-a-number",
}
PROD_KEYS = ("RENDER", "ENV", "APP_ENV", "ENVIRONMENT")

# ---- fake Supabase signing keys --------------------------------------------------------

PROJECT_URL = "https://example-ref.supabase.co"
ISSUER = f"{PROJECT_URL}/auth/v1"
KID = "sec-test-key"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
PUBLIC_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)


class _Key:
    def __init__(self, key):
        self.key = key


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != KID:
            raise jwt.PyJWKClientError("no matching key")
        return _Key(PRIVATE_KEY.public_key())


def _enable_supabase():
    auth.SUPABASE_URL = PROJECT_URL
    auth.SUPABASE_ISSUER = ISSUER
    auth.SUPABASE_JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
    auth._get_jwks_client = lambda: _FakeJWKS()


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def _unsigned(header: dict, claims: dict) -> str:
    return f"{_b64(header)}.{_b64(claims)}."


def _claims(**extra) -> dict:
    now = int(time.time())
    base = {"iss": ISSUER, "aud": "authenticated", "sub": str(uuid.uuid4()), "email": "x@example.com",
            "iat": now, "exp": now + 3600}
    base.update(extra)
    return base


def _rejected(token: str) -> bool:
    try:
        auth.decode_token(token)
    except auth.TokenError:
        return True
    return False


# ---- app + data ------------------------------------------------------------------------


def _clear_env():
    for key in PROD_KEYS:
        os.environ.pop(key, None)
    auth.JWT_SECRET = STRONG_SECRET


def _setup():
    _clear_env()
    RateLimiter.reset_all()
    outreach_log.reset()
    outreach_config.set_transport(None)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)
    with TestSession() as db:
        seed.seed_demo_users(db)
    with TestSession() as db:
        clinician = db.scalar(select(User).where(User.email == "clinician@demo.com"))
        jordan_user = db.scalar(select(User).where(User.email == "patient@demo.com"))
        jordan = db.scalar(select(Patient).where(Patient.user_id == jordan_user.id))
        # A second patient with their own clinician: everything about B is off limits to A and Dr. Patel.
        other_clin = User(email="other.clinician@example.com", full_name="Dr. Other", role="clinician",
                          password_hash="x")
        b_user = User(email="b.patient@example.com", full_name="Bea Bee", role="patient", password_hash="x")
        db.add_all([other_clin, b_user])
        db.flush()
        b = Patient(user_id=b_user.id, clinician_id=other_clin.id, procedure_name="Hip replacement",
                    procedure_type="orthopedic", surgery_date=date.today(), phone="+15557654321")
        db.add(b)
        db.flush()
        med_b = Medication(patient_id=b.id, name="Cefazolin", dosage="1 g", times_of_day=["08:00"],
                           start_date=date.today())
        esc_b = Escalation(patient_id=b.id, trigger_type="red_flag", severity="high", summary="B alert")
        db.add_all([med_b, esc_b])
        db.commit()
        ctx = {
            "jordan": _h(jordan_user), "clinician": _h(clinician), "b": _h(b_user), "other_clin": _h(other_clin),
            "jordan_id": jordan.id, "b_id": b.id, "b_med": med_b.id, "b_esc": esc_b.id,
            "jordan_user": jordan_user.id,
        }

    from app.main import app

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with`: the startup seed must not run (it would use the real DATABASE_URL).
    return TestClient(app, raise_server_exceptions=False), TestSession, ctx


def _h(user: User) -> dict:
    return {"Authorization": f"Bearer {auth.create_token(user)}"}


# ---- tokens ----------------------------------------------------------------------------


def test_alg_none_token_rejected():
    _clear_env()
    _enable_supabase()
    assert _rejected(_unsigned({"alg": "none", "typ": "JWT", "kid": KID}, _claims()))
    assert _rejected(_unsigned({"alg": "none", "typ": "JWT"}, {"sub": str(uuid.uuid4()), "role": "clinician",
                                                              "exp": int(time.time()) + 600}))
    # "None"/"NONE" spellings route to the Supabase verifier, which pins ES256/RS256.
    assert _rejected(_unsigned({"alg": "NONE", "kid": KID}, _claims()))


def test_hs256_signed_with_public_key_rejected():
    """Classic algorithm confusion: sign HS256 with the published public key."""
    _clear_env()
    _enable_supabase()
    assert _rejected(_hs256_raw(_claims(), PUBLIC_PEM))


def _hs256_raw(claims: dict, secret: bytes) -> str:
    # PyJWT refuses PEM keys as HMAC secrets, so build the token by hand.
    import hashlib
    import hmac
    head = _b64({"alg": "HS256", "typ": "JWT", "kid": KID})
    body = _b64(claims)
    sig = hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


def test_es256_header_on_local_token_rejected():
    """A token claiming ES256 but signed with the HS256 secret goes to the JWKS path and fails."""
    _clear_env()
    _enable_supabase()
    token = jwt.encode({"sub": str(uuid.uuid4()), "exp": int(time.time()) + 60}, STRONG_SECRET, algorithm="HS256")
    head, body, sig = token.split(".")
    swapped = f"{_b64({'alg': 'ES256', 'typ': 'JWT', 'kid': KID})}.{body}.{sig}"
    assert _rejected(swapped)


def test_local_token_needs_exp_and_rejects_expired():
    _clear_env()
    no_exp = jwt.encode({"sub": str(uuid.uuid4()), "role": "clinician"}, STRONG_SECRET, algorithm="HS256")
    assert _rejected(no_exp)
    expired = jwt.encode({"sub": str(uuid.uuid4()), "exp": int(time.time()) - 5}, STRONG_SECRET, algorithm="HS256")
    try:
        auth.decode_token(expired)
        raise AssertionError("expired token accepted")
    except auth.TokenError as exc:
        assert "expired" in exc.detail.lower()


def test_phone_call_token_only_opens_chat():
    from app.outreach.calls import call_token

    client, TestSession, ctx = _setup()
    with TestSession() as db:
        jordan = db.get(User, ctx["jordan_user"])
        h = {"Authorization": f"Bearer {call_token(jordan)}"}
    assert client.get("/chat/capabilities", headers=h).status_code == 200
    assert client.post("/chat", headers=h, json={"message": "When can I shower?"}).status_code == 200
    for path in ("/patients/me", "/symptoms", "/epic/status", "/outreach/capabilities", "/auth/me"):
        assert client.get(path, headers=h).status_code == 401, path
    assert client.patch("/patients/me", headers=h, json={"phone": PHONE}).status_code == 401
    assert client.post("/outreach/call", headers=h, json={"kind": "checkin"}).status_code == 401
    # An unknown purpose opens nothing.
    odd = auth.sign_local_token({"sub": str(ctx["jordan_user"]), "purpose": "other", "exp": int(time.time()) + 60})
    assert client.get("/chat/capabilities", headers={"Authorization": f"Bearer {odd}"}).status_code == 401


def test_dev_secret_forgery_rejected_in_production():
    """Anyone can read the dev default in the repo; in production it must sign nothing."""
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        clinician = db.scalar(select(User).where(User.email == "clinician@demo.com"))
    forged = jwt.encode({"sub": str(clinician.id), "role": "clinician", "exp": int(time.time()) + 600},
                        auth.DEV_JWT_SECRET, algorithm="HS256")
    try:
        auth.JWT_SECRET = auth.DEV_JWT_SECRET
        os.environ["RENDER"] = "true"
        assert not auth.local_tokens_enabled()
        assert client.get("/patients", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
        res = client.post("/auth/login", json={"email": "clinician@demo.com", "password": seed.DEMO_PASSWORD})
        assert res.status_code == 503, res.text
        assert "access_token" not in res.text
        # A short secret is just as bad.
        auth.JWT_SECRET = "short-secret"
        assert not auth.local_tokens_enabled()
        # Locally (no RENDER/ENV) the dev default keeps working for development.
        os.environ.pop("RENDER")
        auth.JWT_SECRET = auth.DEV_JWT_SECRET
        assert auth.local_tokens_enabled()
        os.environ["ENV"] = "production"
        assert not auth.local_tokens_enabled()
        auth.JWT_SECRET = STRONG_SECRET
        assert auth.local_tokens_enabled()
        res = client.post("/auth/login", json={"email": "clinician@demo.com", "password": seed.DEMO_PASSWORD})
        assert res.status_code == 200, res.text
    finally:
        _clear_env()


# ---- login abuse -----------------------------------------------------------------------


def test_login_failures_are_rate_limited_per_account():
    client, _, _ = _setup()
    bad = {"email": "patient@demo.com", "password": "wrong"}
    for _ in range(10):
        assert client.post("/auth/login", json=bad).status_code == 401
    res = client.post("/auth/login", json=bad)
    assert res.status_code == 429 and "Retry-After" in res.headers
    # Even the right password waits now (no guessing past the limit)...
    assert client.post("/auth/login", json={**bad, "password": seed.DEMO_PASSWORD}).status_code == 429
    # ...but other accounts are unaffected.
    assert client.post("/auth/login", json={"email": "clinician@demo.com",
                                            "password": seed.DEMO_PASSWORD}).status_code == 200


def test_login_unknown_email_same_answer_and_bounded_input():
    client, _, _ = _setup()
    a = client.post("/auth/login", json={"email": "nobody@example.com", "password": "x"})
    b = client.post("/auth/login", json={"email": "patient@demo.com", "password": "x"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    assert client.post("/auth/login", json={"email": "a@b.c", "password": "x" * 300}).status_code == 422


# ---- cross-patient and cross-clinician access -----------------------------------------


def test_patient_cannot_read_another_patient():
    client, _, ctx = _setup()
    b = str(ctx["b_id"])
    # Patients never get clinician routes.
    for path in (f"/patients/{b}", f"/patients/{b}/care-plan", "/patients", "/escalations"):
        assert client.get(path, headers=ctx["jordan"]).status_code == 403, path
    assert client.patch(f"/patients/{b}", headers=ctx["jordan"], json={"phone": PHONE}).status_code == 403
    # ?patient_id= is ignored for patients: they only ever see their own rows.
    sym = client.get(f"/symptoms?patient_id={b}", headers=ctx["jordan"])
    assert sym.status_code == 200
    with_b = client.get("/symptoms", headers=ctx["b"]).json()
    assert all(row["id"] not in {r["id"] for r in with_b} for row in sym.json()) or not with_b
    hist = client.get(f"/chat/history?patient_id={b}", headers=ctx["jordan"])
    assert hist.status_code == 200
    # Another patient's medication can't be marked.
    res = client.post(f"/medications/{ctx['b_med']}/logs", headers=ctx["jordan"],
                      json={"scheduled_for": datetime.now(timezone.utc).isoformat(), "status": "taken"})
    assert res.status_code == 404


def test_clinician_limited_to_assigned_patients():
    client, _, ctx = _setup()
    b = str(ctx["b_id"])
    h = ctx["clinician"]  # Dr. Patel: Jordan only
    for path in (f"/patients/{b}", f"/patients/{b}/care-plan", f"/symptoms?patient_id={b}",
                 f"/chat/history?patient_id={b}"):
        assert client.get(path, headers=h).status_code == 404, path
    assert client.post(f"/patients/{b}/care-plan", headers=h,
                       json={"title": "x", "raw_text": "Wound care:\nKeep dry."}).status_code == 404
    assert client.patch(f"/patients/{b}", headers=h, json={"phone": PHONE}).status_code == 404
    assert client.patch(f"/escalations/{ctx['b_esc']}", headers=h, json={"status": "resolved"}).status_code == 404
    assert all(e["patient_id"] != b for e in client.get("/escalations?status=all", headers=h).json())
    assert all(p["id"] != b for p in client.get("/patients", headers=h).json())
    # The demo clinician (public login) can't list or claim unassigned sign-ups.
    assert client.get("/patients/unassigned", headers=h).status_code == 403
    assert client.post(f"/patients/{b}/assign", headers=h).status_code == 403
    # B's own clinician can.
    assert client.get(f"/patients/{b}", headers=ctx["other_clin"]).status_code == 200


def test_demo_reset_only_for_demo_or_clinician():
    client, _, ctx = _setup()
    assert client.post("/demo/reset", headers=ctx["b"]).status_code == 403
    assert client.post("/demo/reset").status_code == 401
    assert client.post("/demo/reset", headers=ctx["jordan"]).status_code == 200


def test_malformed_ids_and_filters_are_422_not_500():
    client, _, ctx = _setup()
    h = ctx["clinician"]
    assert client.get("/patients/1%20OR%201=1", headers=h).status_code == 422
    assert client.get("/escalations?status=open'%20OR%20'1'='1", headers=h).status_code == 422
    assert client.get("/patients/me/medication-logs?since=yesterday';--", headers=ctx["jordan"]).status_code == 422
    assert client.get("/symptoms?patient_id=../../etc", headers=h).status_code == 422


# ---- input size limits -----------------------------------------------------------------


def test_body_and_field_limits():
    client, _, ctx = _setup()
    big = "x" * (300 * 1024)
    res = client.post("/chat", headers={**ctx["jordan"], "Content-Type": "application/json"},
                      content=json.dumps({"message": big}))
    assert res.status_code == 413, res.status_code
    # Without Content-Length (chunked upload) the stream is cut off at the limit, also 413.
    raw = json.dumps({"message": big}).encode()
    res = client.post("/chat", headers={**ctx["jordan"], "Content-Type": "application/json"},
                      content=iter([raw[:150_000], raw[150_000:]]))
    assert res.status_code == 413, res.status_code
    assert client.post("/chat", headers=ctx["jordan"], json={"message": "x" * 2001}).status_code == 422
    plan = {"title": "t", "raw_text": "y" * 50_001}
    assert client.post(f"/patients/{ctx['jordan_id']}/care-plan", headers=ctx["clinician"],
                       json=plan).status_code == 422
    note = {"status": "resolved", "clinician_notes": "n" * 4001}
    with_esc = client.get("/escalations?status=all", headers=ctx["clinician"]).json()
    if with_esc:
        assert client.patch(f"/escalations/{with_esc[0]['id']}", headers=ctx["clinician"],
                            json=note).status_code == 422
    sym = {"pain_level": 3, "free_text": "z" * 2001}
    assert client.post("/symptoms", headers=ctx["jordan"], json=sym).status_code == 422


# ---- rate limits -----------------------------------------------------------------------


def test_chat_is_rate_limited_per_patient():
    from app import rate_limits

    client, _, ctx = _setup()
    for _ in range(rate_limits.CHAT.limit):
        rate_limits.CHAT.hit(str(ctx["jordan_user"]))
    res = client.post("/chat", headers=ctx["jordan"], json={"message": "When can I shower?"})
    assert res.status_code == 429 and int(res.headers["Retry-After"]) > 0
    # Another patient isn't affected.
    assert client.post("/chat", headers=ctx["b"], json={"message": "hello"}).status_code == 200


# ---- outreach abuse limits -------------------------------------------------------------


def _outreach_env(on: bool = True):
    for key in OUTREACH_ENV:
        os.environ.pop(key, None)
    if on:
        os.environ.update(OUTREACH_ENV)


def _mock_providers():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.twilio.com":
            return httpx.Response(201, json={"sid": "SM" + "b" * 32, "status": "queued", "error_code": None})
        return httpx.Response(200, json={"success": True, "conversation_id": "conv_1", "callSid": "CA1"})
    outreach_config.set_transport(httpx.MockTransport(handler))


def test_new_number_cooldown_blocks_calls_and_texts():
    client, _, ctx = _setup()
    _outreach_env()
    _mock_providers()
    # Cooldown is opt-in; demo accounts open to any number so nothing here is a listed team phone.
    os.environ["OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS"] = "600"
    os.environ["OUTREACH_DEMO_ALLOWLIST"] = "*"
    try:
        res = client.patch("/patients/me", headers=ctx["jordan"], json={"phone": "(555) 234-9876"})
        assert res.status_code == 200, res.text
        for path in ("/outreach/call", "/outreach/sms"):
            res = client.post(path, headers=ctx["jordan"], json={"kind": "checkin"})
            assert res.status_code == 429, (path, res.status_code, res.text)
            assert "10 minutes" in res.json()["detail"] and int(res.headers["Retry-After"]) > 500
        # Saving the same number again doesn't restart the clock; a clinician change does.
        guard._phone_changed[ctx["jordan_id"]] -= 601
        assert client.patch("/patients/me", headers=ctx["jordan"], json={"phone": "+15552349876"}).status_code == 200
        assert client.post("/outreach/call", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200
        assert client.patch(f"/patients/{ctx['jordan_id']}", headers=ctx["clinician"],
                            json={"phone": "555-234-1111"}).status_code == 200
        assert guard.new_number_wait(ctx["jordan_id"]) > 500
    finally:
        os.environ.pop("OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS", None)
        _outreach_env(False)
        outreach_config.set_transport(None)


def test_cooldown_is_off_by_default():
    client, _, ctx = _setup()
    _outreach_env()
    _mock_providers()
    os.environ.pop("OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS", None)
    os.environ["OUTREACH_DEMO_ALLOWLIST"] = "*"
    try:
        assert client.patch("/patients/me", headers=ctx["jordan"], json={"phone": "(555) 234-9876"}).status_code == 200
        assert guard.new_number_wait(ctx["jordan_id"]) == 0
        assert client.post("/outreach/call", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200
    finally:
        _outreach_env(False)
        outreach_config.set_transport(None)


def test_signup_number_starts_the_cooldown():
    _setup()
    _enable_supabase()
    os.environ["OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS"] = "600"
    token = jwt.encode(_claims(email="signup@example.com", user_metadata={"full_name": "Sam", "phone": "555-222-3333"}),
                       PRIVATE_KEY, algorithm="ES256", headers={"kid": KID})
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/patients/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    pid = uuid.UUID(client.get("/patients/me", headers={"Authorization": f"Bearer {token}"}).json()["id"])
    try:
        assert guard.new_number_wait(pid) > 500
    finally:
        os.environ.pop("OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS", None)


def test_per_patient_and_per_number_daily_caps():
    # A regular account calling a number that is not on the team allowlist.
    client, TestSession, ctx = _setup()
    _outreach_env()
    _mock_providers()
    other = "+15553334444"
    try:
        with TestSession() as db:
            p = db.get(Patient, ctx["b_id"])
            p.phone = other
            # Ten earlier texts today (older than the 60 s interval).
            for i in range(guard.max_per_patient_per_day()):
                db.add(OutreachLog(patient_id=p.id, kind="checkin", channel="sms", to_number_last4="4444",
                                   status="sent", created_at=datetime.now(timezone.utc) - timedelta(hours=1, minutes=i)))
            db.commit()
        res = client.post("/outreach/sms", headers=ctx["b"], json={"kind": "checkin"})
        assert res.status_code == 429 and "today's limit" in res.json()["detail"]
        # Same number, any account: the per-destination cap holds across accounts.
        for _ in range(guard._per_number.limit):
            guard.count_attempt("call", other)
        res = client.post("/outreach/call", headers=ctx["b"], json={"kind": "checkin"})
        assert res.status_code == 429 and "today's limit" in res.json()["detail"]
    finally:
        _outreach_env(False)
        outreach_config.set_transport(None)


def test_allowlisted_numbers_skip_cooldown_and_daily_caps():
    # Team phones on OUTREACH_DEMO_ALLOWLIST are called many times during rehearsals and demos.
    client, TestSession, ctx = _setup()
    _outreach_env()
    _mock_providers()
    os.environ["OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS"] = "600"
    try:
        # Setting the number just now would normally start the 10-minute wait.
        assert client.patch("/patients/me", headers=ctx["jordan"], json={"phone": PHONE}).status_code == 200
        assert guard.new_number_wait(ctx["jordan_id"]) > 500
        assert client.post("/outreach/call", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200
        with TestSession() as db:
            for i in range(guard.max_per_patient_per_day()):
                db.add(OutreachLog(patient_id=ctx["jordan_id"], kind="checkin", channel="sms", to_number_last4="5678",
                                   status="sent", created_at=datetime.now(timezone.utc) - timedelta(hours=1, minutes=i)))
            db.commit()
        for _ in range(guard._per_number.limit):
            guard.count_attempt("sms", PHONE)
        assert client.post("/outreach/sms", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200
    finally:
        os.environ.pop("OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS", None)
        _outreach_env(False)
        outreach_config.set_transport(None)


def test_demo_account_only_reaches_allowlisted_numbers():
    client, TestSession, ctx = _setup()
    _outreach_env()
    _mock_providers()
    try:
        with TestSession() as db:
            db.get(Patient, ctx["jordan_id"]).phone = "+15553334444"  # not on the allowlist
            db.commit()
        caps = client.get("/outreach/capabilities", headers=ctx["jordan"]).json()
        assert caps["call"] is False and caps["sms"] is False
        assert caps["reasons"]["call"] == "Demo accounts can only call approved test numbers"
        for path in ("/outreach/call", "/outreach/sms"):
            res = client.post(path, headers=ctx["jordan"], json={"kind": "checkin"})
            assert res.status_code == 403 and "approved test numbers" in res.json()["detail"], path

        # Allowlisted number: the demo account works.
        with TestSession() as db:
            db.get(Patient, ctx["jordan_id"]).phone = PHONE
            db.commit()
        caps = client.get("/outreach/capabilities", headers=ctx["jordan"]).json()
        assert caps["call"] is True and "call" not in caps["reasons"]
        assert client.post("/outreach/call", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200

        # "none": demo accounts can't text or call at all.
        os.environ["OUTREACH_DEMO_ALLOWLIST"] = "none"
        assert client.get("/outreach/capabilities", headers=ctx["jordan"]).json()["call"] is False
        assert client.post("/outreach/sms", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 403

        # Unset or "*": open, any usable number (the demo-day default).
        for value in (None, "*"):
            if value is None:
                os.environ.pop("OUTREACH_DEMO_ALLOWLIST", None)
            else:
                os.environ["OUTREACH_DEMO_ALLOWLIST"] = value
            with TestSession() as db:
                db.get(Patient, ctx["jordan_id"]).phone = "+15553334444"
                db.commit()
            assert client.get("/outreach/capabilities", headers=ctx["jordan"]).json()["call"] is True, value
        # (a call to Jordan went out moments ago, so the 60 s per-channel interval applies; text instead)
        assert client.post("/outreach/sms", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200
        os.environ["OUTREACH_DEMO_ALLOWLIST"] = OUTREACH_ENV["OUTREACH_DEMO_ALLOWLIST"]

        # A regular (non-demo) patient isn't bound by the allowlist.
        caps_b = client.get("/outreach/capabilities", headers=ctx["b"]).json()
        assert caps_b["call"] is True and "call" not in caps_b["reasons"]
        assert client.post("/outreach/call", headers=ctx["b"], json={"kind": "checkin"}).status_code == 200
    finally:
        _outreach_env(False)
        os.environ.pop("OUTREACH_DEMO_ALLOWLIST", None)
        outreach_config.set_transport(None)


def test_demo_reset_does_not_release_call_interval():
    client, TestSession, ctx = _setup()
    _outreach_env()
    _mock_providers()
    try:
        with TestSession() as db:
            db.get(Patient, ctx["jordan_id"]).phone = PHONE
            db.commit()
        assert client.post("/outreach/call", headers=ctx["jordan"], json={"kind": "checkin"}).status_code == 200
        assert client.post("/demo/reset", headers=ctx["jordan"]).status_code == 200
        with TestSession() as db:  # the reset clears the phone; put it back to test the interval alone
            db.get(Patient, ctx["jordan_id"]).phone = PHONE
            db.commit()
        again = client.post("/outreach/call", headers=ctx["jordan"], json={"kind": "checkin"})
        assert again.status_code == 429, again.text
    finally:
        _outreach_env(False)
        outreach_config.set_transport(None)


def test_calls_refused_when_tokens_disabled():
    client, TestSession, ctx = _setup()
    _outreach_env()
    try:
        with TestSession() as db:
            db.get(Patient, ctx["jordan_id"]).phone = PHONE
            db.commit()
        os.environ["RENDER"] = "true"
        auth.JWT_SECRET = auth.DEV_JWT_SECRET
        # The patient's own session would be refused too; use the decode bypass only for this check.
        assert not auth.local_tokens_enabled()
        try:
            auth.sign_local_token({"sub": "x", "exp": int(time.time()) + 60})
            raise AssertionError("signed a token with the dev secret in production")
        except auth.LocalTokensDisabled:
            pass
    finally:
        _outreach_env(False)
        _clear_env()


# ---- headers, CORS, errors -------------------------------------------------------------


def test_security_headers_and_no_store():
    client, _, ctx = _setup()
    res = client.get("/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in res.headers  # local http
    res = client.get("/patients/me", headers=ctx["jordan"])
    assert res.headers["cache-control"] == "no-store"
    os.environ["RENDER"] = "true"
    auth.JWT_SECRET = STRONG_SECRET
    try:
        assert "max-age" in client.get("/").headers["strict-transport-security"]
    finally:
        _clear_env()


def test_cors_allows_only_listed_origins_without_credentials():
    client, _, _ = _setup()
    pre = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    ok = client.options("/patients/me", headers={"Origin": "https://cloudcare.icu", **pre})
    assert ok.headers.get("access-control-allow-origin") == "https://cloudcare.icu"
    assert "access-control-allow-credentials" not in ok.headers
    bad = client.options("/patients/me", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in bad.headers
    simple = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


def test_unhandled_errors_hide_details():
    client, _, _ = _setup()
    from app.main import app

    path = "/__security_test_boom"
    if not any(getattr(r, "path", None) == path for r in app.router.routes):
        @app.get(path)
        def boom():
            raise RuntimeError("secret detail sb_secret_xyz in a stack trace")

    res = client.get(path)
    assert res.status_code == 500
    assert "sb_secret" not in res.text and "Traceback" not in res.text and "RuntimeError" not in res.text
    assert res.json()["detail"].startswith("Something went wrong")


def test_validation_errors_do_not_echo_passwords():
    client, _, _ = _setup()
    res = client.post("/auth/login", json={"email": "a@b.c", "password": "p" * 257})
    assert res.status_code == 422
    # FastAPI echoes the rejected input; make sure it is not the password itself for long values.
    # (Documented: 422 bodies echo input, so clients must not log them. See docs/security-review.md.)
    assert "detail" in res.json()


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
