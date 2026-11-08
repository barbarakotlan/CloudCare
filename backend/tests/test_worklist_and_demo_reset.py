"""Clinician worklist urgency fields, unassigned sign-ups, escalation review details,
the demo-patient reset, and fixed reply wording that names no clinician.

In-memory SQLite seeded with the demo data (Supabase seeding switched off, no network).

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_worklist_and_demo_reset.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth, seed  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.models import (  # noqa: E402
    Appointment, CarePlan, CarePlanChunk, ChatMessage, ChatSession, EpicConnection, Escalation, Medication,
    MedicationLog, OutreachLog, Patient, RiskScore, SymptomLog, User,
)
from app.routes.patients import _worklist_order  # noqa: E402
from app.schemas import PatientRow, RiskOut  # noqa: E402

os.environ["LLM_PROVIDER"] = "none"
seed.ensure_supabase_demo_users = lambda db: {}


def _client(TestSession):
    from app.main import app

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with` block: skips the app's startup seed so this test owns the database.
    return TestClient(app)


def _setup(seeded: bool = True):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)
    ctx: dict = {}
    if seeded:
        with TestSession() as db:
            seed.seed_demo_users(db)
        with TestSession() as db:
            clinician = db.scalar(select(User).where(User.email == "clinician@demo.com"))
            patient_user = db.scalar(select(User).where(User.email == "patient@demo.com"))
            jordan = db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
            ctx = {
                "clinician": _headers(clinician),
                "patient": _headers(patient_user),
                "clinician_id": clinician.id,
                "jordan_id": jordan.id,
            }
    return _client(TestSession), TestSession, ctx


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {auth.create_token(user)}"}


def _new_user(TestSession, email: str, role: str, full_name: str = "Someone") -> tuple[uuid.UUID, dict]:
    with TestSession() as db:
        user = User(email=email, full_name=full_name, role=role, password_hash="x")
        db.add(user)
        db.commit()
        return user.id, _headers(user)


def _new_patient(TestSession, clinician_id, email="new@example.com", name="New Person") -> str:
    with TestSession() as db:
        user = User(email=email, full_name=name, role="patient", password_hash="x")
        db.add(user)
        db.flush()
        p = Patient(user_id=user.id, clinician_id=clinician_id, procedure_name=auth.PLACEHOLDER_PROCEDURE,
                    procedure_type="unknown", surgery_date=date.today())
        db.add(p)
        db.commit()
        return str(p.id)


def _add_escalation(TestSession, patient_id, severity: str, status: str = "open", **extra) -> str:
    with TestSession() as db:
        e = Escalation(patient_id=patient_id, trigger_type="red_flag", severity=severity, status=status,
                       summary=f"{severity} test alert", **extra)
        db.add(e)
        db.commit()
        return str(e.id)


# ---- GET /patients: urgency fields and order ---------------------------------------

def test_patient_rows_carry_urgency_fields():
    client, TestSession, ctx = _setup()
    rows = client.get("/patients", headers=ctx["clinician"]).json()
    assert rows, "seeded cohort expected"
    for r in rows:
        for key in ("open_emergencies", "open_high", "last_alert_at", "latest_risk_at", "latest_risk",
                    "open_escalations", "last_checkin_at"):
            assert key in r, key
        assert r["open_emergencies"] + r["open_high"] <= r["open_escalations"]
        if r["latest_risk"]:
            assert r["latest_risk_at"] == r["latest_risk"]["created_at"]
        else:
            assert r["latest_risk_at"] is None
    # Rows come back in worklist order.
    as_models = [PatientRow.model_validate(r) for r in rows]
    assert as_models == sorted(as_models, key=_worklist_order)


def test_open_emergency_puts_patient_first_regardless_of_risk():
    client, TestSession, ctx = _setup()
    before = client.get("/patients", headers=ctx["clinician"]).json()
    top_emergencies = max(r["open_emergencies"] for r in before)
    for _ in range(top_emergencies + 1):
        _add_escalation(TestSession, ctx["jordan_id"], "emergency")
    _add_escalation(TestSession, ctx["jordan_id"], "high")
    _add_escalation(TestSession, ctx["jordan_id"], "emergency", status="resolved")  # not counted

    rows = client.get("/patients", headers=ctx["clinician"]).json()
    first = rows[0]
    assert first["id"] == str(ctx["jordan_id"])
    assert first["open_emergencies"] == top_emergencies + 1
    assert first["open_high"] == 1
    assert first["open_escalations"] == top_emergencies + 2
    assert first["last_alert_at"] is not None


def test_worklist_order_tiebreaks():
    now = datetime.now(timezone.utc)

    def row(name, em=0, high=0, open_=0, score=None):
        risk = RiskOut(score=score, risk_level="low", top_factors=[], model_version="t", created_at=now) \
            if score is not None else None
        return PatientRow(id=uuid.uuid4(), full_name=name, procedure_name="x", surgery_date=date.today(),
                          latest_risk=risk, open_escalations=open_, open_emergencies=em, open_high=high,
                          last_checkin_at=None)

    rows = [
        row("Zed", score=0.9),
        row("amy", score=0.2),
        row("Bob", open_=1, score=0.1),
        row("Cat", high=1, open_=1, score=0.05),
        row("Dan", em=1, open_=1),
        row("Eve", high=2, open_=2),
        row("Abe"),
        row("Al", score=0.2),
    ]
    order = [r.full_name for r in sorted(rows, key=_worklist_order)]
    assert order == ["Dan", "Eve", "Cat", "Bob", "Zed", "Al", "amy", "Abe"], order


def test_patients_list_excludes_unassigned():
    client, TestSession, ctx = _setup()
    unassigned_id = _new_patient(TestSession, None)
    ids = {r["id"] for r in client.get("/patients", headers=ctx["clinician"]).json()}
    assert unassigned_id not in ids
    assert str(ctx["jordan_id"]) in ids


# ---- GET /patients/unassigned and POST /patients/{id}/assign -------------------------

def test_unassigned_list_and_claim():
    client, TestSession, ctx = _setup()
    pid = _new_patient(TestSession, None, name="Real Signup")
    doc_id, doc = _new_user(TestSession, "real.doc@example.com", "clinician", "Dr. Real")
    listed = client.get("/patients/unassigned", headers=doc)
    assert listed.status_code == 200, listed.text
    assert [r["id"] for r in listed.json()] == [pid]
    assert listed.json()[0]["full_name"] == "Real Signup"

    res = client.post(f"/patients/{pid}/assign", headers=doc)
    assert res.status_code == 200, res.text
    assert res.json()["id"] == pid
    # Idempotent for the same clinician.
    assert client.post(f"/patients/{pid}/assign", headers=doc).status_code == 200
    with TestSession() as db:
        assert db.get(Patient, uuid.UUID(pid)).clinician_id == doc_id
    assert pid in {r["id"] for r in client.get("/patients", headers=doc).json()}
    assert client.get("/patients/unassigned", headers=doc).json() == []
    # The demo clinician never sees the claimed patient.
    assert pid not in {r["id"] for r in client.get("/patients", headers=ctx["clinician"]).json()}


def test_demo_clinician_cannot_see_or_claim_signups():
    client, TestSession, ctx = _setup()
    pid = _new_patient(TestSession, None, name="Real Signup")
    listed = client.get("/patients/unassigned", headers=ctx["clinician"])
    assert listed.status_code == 403 and listed.json()["detail"] == "Demo accounts can't claim patients"
    claim = client.post(f"/patients/{pid}/assign", headers=ctx["clinician"])
    assert claim.status_code == 403 and claim.json()["detail"] == "Demo accounts can't claim patients"
    with TestSession() as db:
        assert db.get(Patient, uuid.UUID(pid)).clinician_id is None
    assert pid not in {r["id"] for r in client.get("/patients", headers=ctx["clinician"]).json()}


def test_assign_refuses_other_clinicians_patient_and_unknown():
    client, TestSession, ctx = _setup()
    _, other = _new_user(TestSession, "other.doc@example.com", "clinician", "Dr. Other")
    assert client.post(f"/patients/{ctx['jordan_id']}/assign", headers=other).status_code == 409
    assert client.post(f"/patients/{uuid.uuid4()}/assign", headers=other).status_code == 404
    with TestSession() as db:
        assert db.get(Patient, ctx["jordan_id"]).clinician_id == ctx["clinician_id"]


def test_unassigned_routes_are_clinician_only():
    client, TestSession, ctx = _setup()
    pid = _new_patient(TestSession, None)
    assert client.get("/patients/unassigned", headers=ctx["patient"]).status_code == 403
    assert client.get("/patients/unassigned").status_code == 401
    assert client.post(f"/patients/{pid}/assign", headers=ctx["patient"]).status_code == 403


# ---- Escalation review details ---------------------------------------------------------

def test_acknowledge_records_who_and_when():
    client, TestSession, ctx = _setup()
    eid = _add_escalation(TestSession, ctx["jordan_id"], "high")
    fresh = next(e for e in client.get("/escalations", headers=ctx["clinician"]).json() if e["id"] == eid)
    assert fresh["reviewed_by_name"] is None and fresh["acknowledged_at"] is None

    ack = client.patch(f"/escalations/{eid}", headers=ctx["clinician"], json={"status": "acknowledged"})
    assert ack.status_code == 200, ack.text
    body = ack.json()
    assert body["reviewed_by_name"] == "Dr. Priya Patel"
    assert body["acknowledged_at"] is not None and body["resolved_at"] is None
    first_ack = body["acknowledged_at"]

    # Acknowledging again (e.g. adding a note) keeps the original time.
    again = client.patch(f"/escalations/{eid}", headers=ctx["clinician"],
                         json={"status": "acknowledged", "clinician_notes": "Called back"}).json()
    assert again["acknowledged_at"] == first_ack

    resolved = client.patch(f"/escalations/{eid}", headers=ctx["clinician"],
                            json={"status": "resolved", "clinician_notes": "Fine"}).json()
    assert resolved["acknowledged_at"] == first_ack and resolved["resolved_at"] is not None
    listed = next(e for e in client.get("/escalations?status=all", headers=ctx["clinician"]).json()
                  if e["id"] == eid)
    assert listed["reviewed_by_name"] == "Dr. Priya Patel" and listed["acknowledged_at"] == first_ack

    reopened = client.patch(f"/escalations/{eid}", headers=ctx["clinician"], json={"status": "open"}).json()
    assert reopened["acknowledged_at"] is None and reopened["resolved_at"] is None


def test_resolve_without_acknowledge_leaves_acknowledged_at_empty():
    client, TestSession, ctx = _setup()
    eid = _add_escalation(TestSession, ctx["jordan_id"], "low")
    res = client.patch(f"/escalations/{eid}", headers=ctx["clinician"], json={"status": "resolved"}).json()
    assert res["acknowledged_at"] is None and res["reviewed_by_name"] == "Dr. Priya Patel"


# ---- POST /demo/reset -------------------------------------------------------------------

def _fill_activity(TestSession, patient_id) -> None:
    """One row of everything the reset clears."""
    now = datetime.now(timezone.utc)
    with TestSession() as db:
        log = SymptomLog(patient_id=patient_id, source="checkin", pain_level=9, shortness_of_breath=True)
        db.add(log)
        db.flush()
        risk = RiskScore(patient_id=patient_id, symptom_log_id=log.id, score=0.9, risk_level="high",
                         model_version="t", top_factors=[])
        msg = ChatMessage(patient_id=patient_id, role="patient", content="hello", citations=[])
        db.add_all([risk, msg])
        db.flush()
        db.add(Escalation(patient_id=patient_id, trigger_type="red_flag", severity="emergency", status="open",
                          summary="x", chat_message_id=msg.id, risk_score_id=risk.id))
        db.add(ChatSession(patient_id=patient_id, pending_action={"kind": "message_care_team"}))
        med = db.scalar(select(Medication).where(Medication.patient_id == patient_id).limit(1))
        if med is not None:
            db.add(MedicationLog(medication_id=med.id, scheduled_for=now.replace(microsecond=0), status="taken",
                                 responded_at=now))
        db.add(OutreachLog(patient_id=patient_id, kind="checkin", channel="call", to_number_last4="1234",
                           status="started"))
        db.commit()


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def test_reset_as_clinician_clears_only_demo_patient_activity():
    client, TestSession, ctx = _setup()
    jordan = ctx["jordan_id"]
    other_id = uuid.UUID(_new_patient(TestSession, ctx["clinician_id"], email="keep@example.com"))
    _fill_activity(TestSession, jordan)
    _fill_activity(TestSession, other_id)
    # A presenter may save their phone and link MyChart, then sign in again (which resets).
    with TestSession() as db:
        p = db.get(Patient, jordan)
        p.phone = "+15551234567"
        db.add(EpicConnection(user_id=p.user_id, iss="https://fhir.example/R4", patient_fhir_id="abc",
                              access_token_enc="enc", connected_at=datetime.now(timezone.utc)))
        db.commit()
    with TestSession() as db:
        keep = {
            "plans": _count(db, CarePlan, CarePlan.patient_id == jordan),
            "chunks": _count(db, CarePlanChunk, CarePlanChunk.patient_id == jordan),
            "meds": _count(db, Medication, Medication.patient_id == jordan),
            "appts": _count(db, Appointment, Appointment.patient_id == jordan),
            "users": _count(db, User),
        }
        other_before = {
            "esc": _count(db, Escalation, Escalation.patient_id == other_id),
            "chat": _count(db, ChatMessage, ChatMessage.patient_id == other_id),
            "out": _count(db, OutreachLog, OutreachLog.patient_id == other_id),
        }

    res = client.post("/demo/reset", headers=ctx["clinician"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reset"] is True
    assert set(body["counts"]) == {"chat_messages", "chat_sessions", "symptom_logs", "risk_scores", "escalations",
                                   "medication_logs", "outreach_log"}
    assert body["counts"]["chat_sessions"] == 1 and body["counts"]["outreach_log"] == 1
    assert body["counts"]["medication_logs"] == 1 and body["counts"]["escalations"] >= 1
    assert body["counts"]["symptom_logs"] >= 3  # two seeded + one added
    assert body["restored"] == {"symptom_logs": 2, "risk_scores": 2}

    with TestSession() as db:
        assert _count(db, ChatMessage, ChatMessage.patient_id == jordan) == 0
        assert _count(db, ChatSession, ChatSession.patient_id == jordan) == 0
        assert _count(db, Escalation, Escalation.patient_id == jordan) == 0
        assert _count(db, OutreachLog, OutreachLog.patient_id == jordan) == 0
        med_ids = select(Medication.id).where(Medication.patient_id == jordan)
        assert _count(db, MedicationLog, MedicationLog.medication_id.in_(med_ids)) == 0
        # Baseline check-ins are back, each with a low risk score.
        assert _count(db, SymptomLog, SymptomLog.patient_id == jordan) == 2
        levels = db.scalars(select(RiskScore.risk_level).where(RiskScore.patient_id == jordan)).all()
        assert len(levels) == 2 and "high" not in levels
        # Left alone: account, plan, medications, appointments, and other patients.
        assert keep == {
            "plans": _count(db, CarePlan, CarePlan.patient_id == jordan),
            "chunks": _count(db, CarePlanChunk, CarePlanChunk.patient_id == jordan),
            "meds": _count(db, Medication, Medication.patient_id == jordan),
            "appts": _count(db, Appointment, Appointment.patient_id == jordan),
            "users": _count(db, User),
        }
        assert other_before == {
            "esc": _count(db, Escalation, Escalation.patient_id == other_id),
            "chat": _count(db, ChatMessage, ChatMessage.patient_id == other_id),
            "out": _count(db, OutreachLog, OutreachLog.patient_id == other_id),
        }
        jordan_row = db.get(Patient, jordan)
        assert jordan_row is not None
        # The stored phone and the MyChart link survive a reset.
        assert jordan_row.phone == "+15551234567"
        assert _count(db, EpicConnection, EpicConnection.user_id == jordan_row.user_id) == 1

    # The worklist still works and the demo patient has a fresh low risk, no open alerts.
    row = next(r for r in client.get("/patients", headers=ctx["clinician"]).json() if r["id"] == str(jordan))
    assert row["open_escalations"] == 0 and row["latest_risk"]["risk_level"] != "high"
    # Chat history is empty for the patient.
    assert client.get("/chat/history", headers=ctx["patient"]).json() == []


def test_reset_allowed_for_demo_patient_and_refused_for_others():
    client, TestSession, ctx = _setup()
    _fill_activity(TestSession, ctx["jordan_id"])
    as_patient = client.post("/demo/reset", headers=ctx["patient"])
    assert as_patient.status_code == 200, as_patient.text
    assert as_patient.json()["counts"]["chat_messages"] == 1

    _, real_patient = _new_user(TestSession, "someone@example.com", "patient")
    assert client.post("/demo/reset", headers=real_patient).status_code == 403
    assert client.post("/demo/reset").status_code == 401
    # Running it twice is fine.
    second = client.post("/demo/reset", headers=ctx["clinician"])
    assert second.status_code == 200 and second.json()["counts"]["chat_messages"] == 0


def test_reset_404_without_demo_patient():
    client, TestSession, _ = _setup(seeded=False)
    _, doc = _new_user(TestSession, "doc@example.com", "clinician", "Dr. Doc")
    res = client.post("/demo/reset", headers=doc)
    assert res.status_code == 404 and res.json()["detail"] == "Demo patient not found"


# ---- Fixed reply wording names no clinician ---------------------------------------------

def test_fixed_wording_names_no_clinician():
    app_dir = BACKEND_DIR / "app"
    files = [
        *sorted((app_dir / "services" / "foggy").glob("*.py")),
        app_dir / "services" / "ai_service.py",
        app_dir / "outreach" / "sms.py",
        app_dir / "outreach" / "calls.py",
        app_dir / "outreach" / "router.py",
        app_dir / "routes" / "chat.py",
    ]
    named = re.compile(r"Patel|\bDr\.? [A-Z][a-z]+")
    hits = []
    for path in files:
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if named.search(line):
                hits.append(f"{path.name}:{no}: {line.strip()}")
    assert not hits, hits

    from app.outreach import sms
    from app.services.foggy import phrase
    samples = [
        phrase.IDENTITY, phrase.OFFER, phrase.SENT, phrase.SEND_FAILED, phrase.CAPABILITY,
        phrase.refuse_dose_change(True), phrase.refuse_dose_change(False),
        phrase.call_surgeon(["fever"], "fever over 101.5")[0], phrase.call_surgeon(["fall"], "")[0],
        *(phrase.not_in_plan(k, "wine", "Jordan", "sister")[0] for k in (
            "missed_dose", "dose_interval_or_max", "second_opinion", "family_member", "non_medical", "feelings",
            "alcohol_or_cannabis", "unlisted_medication", "other_medical", "other")),
        sms.build_body("checkin", "Jordan Lee", "https://cloudcare.icu"),
        sms.build_body("plan_summary", "Jordan Lee", "https://cloudcare.icu", ["Wound care"]),
    ]
    for text in samples:
        assert not named.search(text), text
        assert "care team" in text or "surgeon" in text or "medical team" in text or "CloudCare" in text \
            or "recovery" in text or "care plan" in text, text


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
