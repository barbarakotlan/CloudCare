"""Texts and calls to the patient's own phone, with Twilio and ElevenLabs mocked.

In-memory SQLite seeded with the demo data; a small app that mounts only the
outreach router. No request ever leaves the process (httpx.MockTransport).

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_outreach.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import base64
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
import jwt  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth, seed  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.models import CarePlan, Patient, User  # noqa: E402
from app.models.outreach import OutreachLog  # noqa: E402
from app.outreach import config as outreach_config  # noqa: E402
from app.outreach import log as outreach_log  # noqa: E402
from app.outreach import sms  # noqa: E402
from app.outreach.phone import PhoneError, is_usable_e164, last4, normalize_e164  # noqa: E402
from app.outreach.router import router as outreach_router  # noqa: E402

seed.ensure_supabase_demo_users = lambda db: {}

# Every test seeds a fresh database; hash the demo password once instead of per user
# (scrypt is deliberately slow). Tests sign in with tokens, not passwords.
from app import demo_data  # noqa: E402

_DEMO_HASH = auth.hash_password(seed.DEMO_PASSWORD)
seed.hash_password = lambda password: _DEMO_HASH
demo_data.hash_password = lambda password: _DEMO_HASH

PHONE = "+15552345678"
TWILIO_SID = "AC" + "a" * 32
MESSAGE_SID = "SM" + "b" * 32

ENV = {
    "TWILIO_ACCOUNT_SID": TWILIO_SID,
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_FROM_NUMBER": "+15550001111",
    "ELEVENLABS_API_KEY": "test-eleven-key",
    "ELEVENLABS_AGENT_ID": "agent_test",
    "ELEVENLABS_PHONE_NUMBER_ID": "phnum_test",
    "PUBLIC_APP_URL": "https://cloudcare.icu",
}
ALL_KEYS = list(ENV) + ["TWILIO_MESSAGING_SERVICE_SID", "OUTREACH_ALLOWED_COUNTRY_CODES", "ELEVENLABS_API_BASE",
                        "OUTREACH_MACHINE_DETECTION", "OUTREACH_RINGING_TIMEOUT_SECS"]


def _env(configured: bool = True, **overrides):
    for key in ALL_KEYS:
        os.environ.pop(key, None)
    if configured:
        os.environ.update(ENV)
    for key, value in overrides.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


class Recorder:
    """Mock transport that records requests and answers with a canned response."""

    def __init__(self, handler):
        self.requests: list[httpx.Request] = []
        self.handler = handler

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


def _mock(handler) -> Recorder:
    rec = Recorder(handler)
    outreach_config.set_transport(httpx.MockTransport(rec))
    return rec


def _twilio_ok(request: httpx.Request) -> httpx.Response:
    if request.method == "GET":
        return httpx.Response(200, json={"sid": MESSAGE_SID, "status": "delivered", "error_code": None})
    return httpx.Response(201, json={"sid": MESSAGE_SID, "status": "queued", "error_code": None})


def _eleven_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "message": "ok", "conversation_id": "conv_123", "callSid": "CA1"})


def _setup(phone: str | None = PHONE, configured: bool = True):
    _env(configured)
    outreach_log.reset()
    outreach_config.set_transport(None)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)
    with TestSession() as db:
        seed.seed_demo_users(db)
        patient_user = db.scalar(select(User).where(User.email == "patient@demo.com"))
        clinician = db.scalar(select(User).where(User.email == "clinician@demo.com"))
        patient = db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
        patient.phone = phone
        db.commit()
        ctx = {
            "patient": {"Authorization": f"Bearer {auth.create_token(patient_user)}"},
            "clinician": {"Authorization": f"Bearer {auth.create_token(clinician)}"},
            "patient_id": patient.id,
            "user_id": patient_user.id,
        }

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(outreach_router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestSession, ctx


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _capture_logs():
    handler = _ListHandler()
    logger = logging.getLogger("cloudcare.outreach")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return handler, lambda: logger.removeHandler(handler)


# ---- phone numbers -----------------------------------------------------------------

def test_normalize_us_formats():
    for raw in ("(555) 234-5678", "555.234.5678", "5552345678", "1 555 234 5678", "+1 555-234-5678"):
        assert normalize_e164(raw) == PHONE, raw
    assert normalize_e164("+44 7700 900123") == "+447700900123"
    assert last4(PHONE) == "5678"


def test_emergency_and_service_numbers_refused():
    for raw in ("911", "+1911", "112", "999", "+1 911 555 1234", "(411) 555-1234", "555-911-1234",
                "211", "12345", "", None, "+0123456789", "abc", "555-0123"):
        try:
            normalize_e164(raw)
        except PhoneError:
            continue
        raise AssertionError(f"accepted {raw!r}")
    assert not is_usable_e164("911")
    assert not is_usable_e164("(555) 234-5678")  # stored values must already be E.164
    assert is_usable_e164(PHONE)


# ---- capabilities ------------------------------------------------------------------

def test_capabilities_not_configured():
    client, _, ctx = _setup(configured=False)
    res = client.get("/outreach/capabilities", headers=ctx["patient"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sms"] is False and body["call"] is False
    assert body["reasons"]["sms"] == "Texting isn't set up on this server yet."
    assert body["reasons"]["call"] == "Phone calls aren't set up on this server yet."
    assert body["phone_on_file"] is True and body["phone_last4"] == "5678"
    assert body["limits"] == {"sms_seconds": 60, "call_seconds": 120}


def test_capabilities_configured_and_no_phone():
    client, _, ctx = _setup(phone=None)
    body = client.get("/outreach/capabilities", headers=ctx["patient"]).json()
    assert body["sms"] is True and body["call"] is True
    assert body["phone_on_file"] is False and body["phone_last4"] is None
    assert body["reasons"] == {"phone": "Add your mobile number first."}


def test_messaging_service_counts_as_sender():
    _env(TWILIO_FROM_NUMBER=None, TWILIO_MESSAGING_SERVICE_SID="MG" + "c" * 32)
    assert outreach_config.get_settings().sms_configured
    _env(TWILIO_FROM_NUMBER=None)
    assert outreach_config.get_settings().sms_missing == ["TWILIO_FROM_NUMBER"]


def test_patients_only():
    client, _, ctx = _setup()
    assert client.get("/outreach/capabilities").status_code == 401
    assert client.get("/outreach/capabilities", headers=ctx["clinician"]).status_code == 403
    assert client.post("/outreach/sms", headers=ctx["clinician"], json={"kind": "checkin"}).status_code == 403
    assert client.post("/outreach/call", headers=ctx["clinician"], json={"kind": "checkin"}).status_code == 403


# ---- texts -------------------------------------------------------------------------

def test_sms_not_configured_sends_nothing():
    client, _, ctx = _setup(configured=False)
    rec = _mock(_twilio_ok)
    res = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    assert res.status_code == 503 and res.json()["detail"] == "Texting isn't set up on this server yet."
    assert rec.requests == []


def test_sms_needs_a_usable_number():
    for phone, detail in ((None, "Add your mobile number first."),
                          ("911", "Your saved number can't receive texts or calls from CloudCare. Update it and try again."),
                          ("+447700900123", "CloudCare can only text or call US numbers right now.")):
        client, _, ctx = _setup(phone=phone)
        rec = _mock(_twilio_ok)
        res = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
        assert res.status_code == 409, (phone, res.text)
        assert res.json()["detail"] == detail
        assert rec.requests == []


def test_sms_sent_to_own_number_with_basic_auth():
    client, TestSession, ctx = _setup()
    rec = _mock(_twilio_ok)
    handler, stop = _capture_logs()
    try:
        res = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    finally:
        stop()
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "sent", "provider_id": MESSAGE_SID, "to_last4": "5678", "detail": None}

    assert len(rec.requests) == 1
    req = rec.requests[0]
    assert req.method == "POST"
    assert str(req.url) == f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    expected = base64.b64encode(f"{TWILIO_SID}:test-twilio-token".encode()).decode()
    assert req.headers["Authorization"] == f"Basic {expected}"
    form = {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
    assert form["To"] == PHONE and form["From"] == "+15550001111"
    assert len(form["Body"]) <= 320 and form["Body"].isascii()
    assert "https://cloudcare.icu/patient/dashboard#check-in" in form["Body"]
    assert form["Body"].startswith("Hi Jordan,")
    assert "911" in form["Body"] and "STOP" in form["Body"]

    with TestSession() as db:
        rows = db.scalars(select(OutreachLog)).all()
        assert len(rows) == 1
        row = rows[0]
        assert (row.channel, row.kind, row.status, row.to_number_last4, row.provider_id) == (
            "sms", "checkin", "sent", "5678", MESSAGE_SID)
    # Logs carry event names and the last four digits only.
    joined = "\n".join(handler.messages)
    assert "5552345678" not in joined and "Jordan" not in joined
    assert any(m.startswith("outreach.sms.sent") and m.endswith("...5678") for m in handler.messages)


def test_sms_plan_summary_lists_sections():
    client, _, ctx = _setup()
    rec = _mock(_twilio_ok)
    res = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "plan_summary"})
    assert res.status_code == 200 and res.json()["status"] == "sent"
    body = parse_qs(rec.requests[0].content.decode())["Body"][0]
    assert "Wound care" in body and "https://cloudcare.icu/patient/dashboard" in body
    assert len(body) <= 320


def test_sms_plan_summary_without_plan():
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        for plan in db.scalars(select(CarePlan).where(CarePlan.patient_id == ctx["patient_id"])):
            plan.is_active = False
        db.commit()
    rec = _mock(_twilio_ok)
    client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "plan_summary"})
    body = parse_qs(rec.requests[0].content.decode())["Body"][0]
    assert "hasn't added your care plan yet" in body


def test_body_builder_caps_length():
    long_sections = [f"Section number {i} with a long name" for i in range(30)]
    body = sms.build_body("plan_summary", "Bartholomew-Alexander Longname", "https://cloudcare.icu", long_sections)
    assert len(body) <= 320 and body.endswith("Reply STOP to opt out.")
    assert sms.build_body("checkin", "", "https://x.test").startswith("Hi there,")


def test_sms_rate_limited_to_one_per_minute():
    client, TestSession, ctx = _setup()
    rec = _mock(_twilio_ok)
    first = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    second = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "plan_summary"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert 1 <= int(second.headers["Retry-After"]) <= 60
    assert second.json()["detail"].startswith("A text was just sent. Please wait")
    assert len(rec.requests) == 1

    # The database limit holds after a restart (in-memory state cleared).
    outreach_log.reset()
    again = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    assert again.status_code == 429 and len(rec.requests) == 1

    # Once the minute has passed, texting works again.
    outreach_log.reset()
    with TestSession() as db:
        for row in db.scalars(select(OutreachLog)):
            row.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db.commit()
    assert client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"}).status_code == 200
    assert len(rec.requests) == 2


def test_sms_twilio_error_is_reported_truthfully():
    client, TestSession, ctx = _setup()
    _mock(lambda r: httpx.Response(400, json={
        "code": 21608, "message": "The number is unverified.", "status": 400}))
    res = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed" and body["provider_id"] is None
    assert "trial account" in body["detail"]
    with TestSession() as db:
        assert db.scalar(select(OutreachLog.status)) == "failed"


def test_sms_network_error_is_failed():
    client, _, ctx = _setup()

    def boom(request):
        raise httpx.ConnectError("down", request=request)

    _mock(boom)
    body = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"}).json()
    assert body["status"] == "failed" and "couldn't reach" in body["detail"]


def test_sms_status_only_for_own_messages():
    client, TestSession, ctx = _setup()
    rec = _mock(_twilio_ok)
    client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    res = client.get(f"/outreach/sms/{MESSAGE_SID}", headers=ctx["patient"])
    assert res.status_code == 200, res.text
    assert res.json() == {"provider_id": MESSAGE_SID, "delivery": "delivered", "failed": False, "detail": None}
    assert str(rec.requests[-1].url).endswith(f"/Messages/{MESSAGE_SID}.json")

    other_sid = "SM" + "d" * 32
    assert client.get(f"/outreach/sms/{other_sid}", headers=ctx["patient"]).status_code == 404
    assert client.get("/outreach/sms/not-a-sid", headers=ctx["patient"]).status_code == 404


def test_sms_status_reports_carrier_block():
    client, _, ctx = _setup()

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"sid": MESSAGE_SID, "status": "undelivered", "error_code": 30034})
        return _twilio_ok(request)

    _mock(handler)
    client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin"})
    body = client.get(f"/outreach/sms/{MESSAGE_SID}", headers=ctx["patient"]).json()
    assert body["failed"] is True and body["delivery"] == "undelivered"
    assert "A2P 10DLC" in body["detail"]


# ---- calls -------------------------------------------------------------------------

def test_call_started_with_dynamic_variables():
    client, TestSession, ctx = _setup()
    rec = _mock(_eleven_ok)
    res = client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"})
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "started", "conversation_id": "conv_123", "to_last4": "5678", "detail": None}

    req = rec.requests[0]
    assert str(req.url) == "https://api.elevenlabs.io/v1/convai/twilio/outbound-call"
    assert req.headers["xi-api-key"] == "test-eleven-key"
    payload = json.loads(req.content)
    assert payload["agent_id"] == "agent_test"
    assert payload["agent_phone_number_id"] == "phnum_test"
    assert payload["to_number"] == PHONE
    # Machine detection is on by default; machine verdicts (call screeners, voicemail) never hang up.
    assert payload["telephony_call_config"] == {
        "ringing_timeout_secs": 45,
        "twilio_machine_detection": {"mode": "enable", "actions": [{"action": "hang_up", "answered_by": ["fax"]}]},
    }
    variables = payload["conversation_initiation_client_data"]["dynamic_variables"]
    assert variables["patient_name"] == "Jordan" and variables["patient_mode"] == "signed_in"
    assert variables["secret__patient_auth"].startswith("Bearer ")

    token = variables["secret__patient_auth"].removeprefix("Bearer ")
    claims = auth.decode_token(token)
    assert claims["sub"] == str(ctx["user_id"]) and claims["role"] == "patient"
    raw = jwt.decode(token, options={"verify_signature": False})
    assert raw["purpose"] == "phone_call"
    assert raw["exp"] - raw["iat"] <= 30 * 60

    with TestSession() as db:
        row = db.scalar(select(OutreachLog))
        assert (row.channel, row.status, row.provider_id, row.to_number_last4) == ("call", "started", "conv_123", "5678")


def test_call_machine_detection_flag_and_ring_time():
    for flag in ("false", "0", "off"):
        client, _, ctx = _setup()
        _env(True, OUTREACH_MACHINE_DETECTION=flag, OUTREACH_RINGING_TIMEOUT_SECS="30")
        rec = _mock(_eleven_ok)
        assert client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"}).status_code == 200
        payload = json.loads(rec.requests[0].content)
        assert payload["telephony_call_config"] == {"ringing_timeout_secs": 30}, flag

    _env(True, OUTREACH_MACHINE_DETECTION="true", OUTREACH_RINGING_TIMEOUT_SECS="999")
    settings = outreach_config.get_settings()
    assert settings.machine_detection is True and settings.ringing_timeout_secs == 120  # clamped
    _env(True, OUTREACH_RINGING_TIMEOUT_SECS="soon")
    assert outreach_config.get_settings().ringing_timeout_secs == 45
    _env(True, OUTREACH_MACHINE_DETECTION=" ")  # blank = default (on)
    assert outreach_config.get_settings().machine_detection is True


def test_call_refused_by_twilio_is_failed():
    client, _, ctx = _setup()
    _mock(lambda r: httpx.Response(200, json={
        "success": False, "message": "The number is unverified. Trial accounts may only make calls to verified numbers.",
        "conversation_id": None, "callSid": None}))
    body = client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"}).json()
    assert body["status"] == "failed" and "verified in Twilio" in body["detail"]


def test_call_http_errors():
    for code, phrase in ((401, "ElevenLabs key"), (404, "agent or phone number"), (500, "couldn't start the call")):
        client, _, ctx = _setup()
        _mock(lambda r, code=code: httpx.Response(code, json={"detail": "nope"}))
        body = client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"}).json()
        assert body["status"] == "failed" and phrase in body["detail"], (code, body)


def test_call_rate_limited_and_never_to_bad_numbers():
    client, _, ctx = _setup()
    rec = _mock(_eleven_ok)
    assert client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"}).status_code == 200
    second = client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"})
    assert second.status_code == 429 and 60 < int(second.headers["Retry-After"]) <= 120
    assert len(rec.requests) == 1

    for phone in (None, "911", "+1911", "+15559111234"):
        client, _, ctx = _setup(phone=phone)
        rec = _mock(_eleven_ok)
        res = client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"})
        assert res.status_code == 409, (phone, res.text)
        assert rec.requests == []


def test_call_not_configured():
    client, _, ctx = _setup(configured=False)
    rec = _mock(_eleven_ok)
    res = client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"})
    assert res.status_code == 503 and res.json()["detail"] == "Phone calls aren't set up on this server yet."
    assert rec.requests == []
    # A config error doesn't use up the patient's slot.
    _env(True)
    assert client.post("/outreach/call", headers=ctx["patient"], json={"kind": "checkin"}).status_code == 200


def test_unknown_kind_rejected():
    client, _, ctx = _setup()
    _mock(_twilio_ok)
    assert client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "anything"}).status_code == 422
    assert client.post("/outreach/call", headers=ctx["patient"], json={"kind": "plan_summary"}).status_code == 422
    # There is no way to choose the destination.
    res = client.post("/outreach/sms", headers=ctx["patient"], json={"kind": "checkin", "to": "+15557654321"})
    assert res.status_code == 200
    assert res.json()["to_last4"] == "5678"


# ---- sign-up phone on first Supabase login -------------------------------------------

def _claims(phone):
    return {
        "provider": "supabase", "sub": str(uuid.uuid4()), "email": f"{uuid.uuid4().hex[:8]}@example.com",
        "role": None, "full_name": "Casey Rivera", "phone": phone,
    }


def test_signup_phone_copied_to_placeholder_patient():
    _, TestSession, _ = _setup()
    with TestSession() as db:
        user = auth._user_from_supabase(db, _claims("(555) 234-5678"))
        patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
        assert patient.procedure_name == auth.PLACEHOLDER_PROCEDURE
        assert patient.phone == PHONE and patient.phone_verified_at is None


def test_signup_phone_invalid_or_missing_is_ignored():
    _, TestSession, _ = _setup()
    with TestSession() as db:
        for raw in ("911", "not a number", None):
            user = auth._user_from_supabase(db, _claims(raw))
            patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
            assert patient is not None and patient.phone is None, raw


# ---- the full app: PATCH /patients/me, phone on PatientOut, router mounted ----------

def _setup_main(phone: str | None = None):
    """Same database, served by the real app (all routers)."""
    from app.main import app

    _, TestSession, ctx = _setup(phone=phone)
    engine_session = TestSession

    def override_get_db():
        db = engine_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with` block: skips the app's startup seed so this test owns the database.
    return TestClient(app), TestSession, ctx


def test_patient_sets_and_clears_own_phone():
    client, TestSession, ctx = _setup_main(phone=None)
    assert client.get("/patients/me", headers=ctx["patient"]).json()["phone"] is None

    res = client.patch("/patients/me", headers=ctx["patient"], json={"phone": "(555) 234-5678"})
    assert res.status_code == 200, res.text
    assert res.json()["phone"] == PHONE and res.json()["full_name"] == "Jordan Lee"
    assert client.get("/patients/me", headers=ctx["patient"]).json()["phone"] == PHONE

    # Sending nothing changes nothing; null clears.
    assert client.patch("/patients/me", headers=ctx["patient"], json={}).json()["phone"] == PHONE
    assert client.patch("/patients/me", headers=ctx["patient"], json={"phone": None}).json()["phone"] is None
    with TestSession() as db:
        assert db.get(Patient, ctx["patient_id"]).phone is None


def test_patient_phone_rejects_service_numbers():
    client, _, ctx = _setup_main(phone=PHONE)
    for raw in ("911", "+1 911 555 1234", "411-555-1234", "12345", "x" * 40):
        res = client.patch("/patients/me", headers=ctx["patient"], json={"phone": raw})
        assert res.status_code == 422, (raw, res.text)
    assert client.get("/patients/me", headers=ctx["patient"]).json()["phone"] == PHONE
    detail = client.patch("/patients/me", headers=ctx["patient"], json={"phone": "911"}).json()["detail"]
    assert detail == "That number can't be used. Enter your own mobile number."


def test_patch_me_is_patient_only():
    client, _, ctx = _setup_main()
    assert client.patch("/patients/me", headers=ctx["clinician"], json={"phone": PHONE}).status_code == 403
    assert client.patch("/patients/me", json={"phone": PHONE}).status_code == 401


def test_clinician_sees_and_edits_phone():
    client, _, ctx = _setup_main(phone=PHONE)
    url = f"/patients/{ctx['patient_id']}"
    assert client.get(url, headers=ctx["clinician"]).json()["phone"] == PHONE
    res = client.patch(url, headers=ctx["clinician"], json={"phone": "555.876.5432"})
    assert res.status_code == 200 and res.json()["phone"] == "+15558765432"
    assert client.patch(url, headers=ctx["clinician"], json={"phone": "911"}).status_code == 422
    assert client.patch(url, headers=ctx["clinician"], json={"phone": ""}).json()["phone"] is None


def test_outreach_router_is_mounted():
    client, _, ctx = _setup_main(phone=PHONE)
    res = client.get("/outreach/capabilities", headers=ctx["patient"])
    assert res.status_code == 200, res.text
    assert res.json()["phone_last4"] == "5678"


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
    _env(False)
    outreach_config.set_transport(None)
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
