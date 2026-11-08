"""Clinician care-plan read, patient profile edit, dose undo, and the chat source tag.

In-memory SQLite seeded with the demo data (Supabase seeding switched off, no network).

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_clinician_routes.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import logging
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth, seed  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.models import Medication, MedicationLog, Patient, User  # noqa: E402

os.environ["LLM_PROVIDER"] = "none"  # chat test uses the keyword fallback; no network
seed.ensure_supabase_demo_users = lambda db: {}


def _setup():
    """Fresh in-memory database with the demo users, patient, plan and medications."""
    from app.main import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)
    with TestSession() as db:
        seed.seed_demo_users(db)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestSession() as db:
        clinician = db.scalar(select(User).where(User.email == "clinician@demo.com"))
        patient_user = db.scalar(select(User).where(User.email == "patient@demo.com"))
        patient = db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
        ctx = {
            "clinician": {"Authorization": f"Bearer {auth.create_token(clinician)}"},
            "patient": {"Authorization": f"Bearer {auth.create_token(patient_user)}"},
            "patient_id": str(patient.id),
            "clinician_id": clinician.id,
        }
    # No `with` block: skips the app's startup seed so this test owns the database.
    return TestClient(app), TestSession, ctx


def _other_clinician_headers(TestSession) -> dict:
    with TestSession() as db:
        other = User(email="other.doc@example.com", full_name="Dr. Other", role="clinician", password_hash="x")
        db.add(other)
        db.commit()
        return {"Authorization": f"Bearer {auth.create_token(other)}"}


# ---- GET /patients/{id}/care-plan --------------------------------------------------

def test_clinician_reads_assigned_patients_care_plan():
    client, _, ctx = _setup()
    res = client.get(f"/patients/{ctx['patient_id']}/care-plan", headers=ctx["clinician"])
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["title"] == "Total Knee Replacement: Home Recovery"
    assert [c["section"] for c in plan["chunks"]] == [
        "Wound care", "Activity", "Pain and swelling", "Medications", "When to call", "After anesthesia",
    ]
    # Same plan the patient sees.
    mine = client.get("/patients/me/care-plan", headers=ctx["patient"]).json()
    assert mine["id"] == plan["id"]


def test_care_plan_reflects_latest_upload():
    client, _, ctx = _setup()
    up = client.post(
        f"/patients/{ctx['patient_id']}/care-plan", headers=ctx["clinician"],
        json={"title": "Updated plan", "raw_text": "Diet:\nEat normally."},
    )
    assert up.status_code == 201, up.text
    res = client.get(f"/patients/{ctx['patient_id']}/care-plan", headers=ctx["clinician"])
    assert res.json()["title"] == "Updated plan"
    assert res.json()["chunks"][0]["section"] == "Diet"


def test_care_plan_null_when_patient_has_none():
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        user = User(email="new@example.com", full_name="New Patient", role="patient", password_hash="x")
        db.add(user)
        db.flush()
        p = Patient(user_id=user.id, clinician_id=ctx["clinician_id"], procedure_name=auth.PLACEHOLDER_PROCEDURE,
                    procedure_type="unknown", surgery_date=date.today())
        db.add(p)
        db.commit()
        new_id = str(p.id)
    res = client.get(f"/patients/{new_id}/care-plan", headers=ctx["clinician"])
    assert res.status_code == 200 and res.json() is None


def test_care_plan_read_is_clinician_and_assignment_only():
    client, TestSession, ctx = _setup()
    url = f"/patients/{ctx['patient_id']}/care-plan"
    assert client.get(url, headers=ctx["patient"]).status_code == 403
    assert client.get(url).status_code == 401
    assert client.get(url, headers=_other_clinician_headers(TestSession)).status_code == 404
    assert client.get(f"/patients/{uuid.uuid4()}/care-plan", headers=ctx["clinician"]).status_code == 404


# ---- PATCH /patients/{id} ---------------------------------------------------------

def test_patch_updates_only_sent_fields():
    client, _, ctx = _setup()
    url = f"/patients/{ctx['patient_id']}"
    before = client.get(url, headers=ctx["clinician"]).json()

    res = client.patch(url, headers=ctx["clinician"], json={"procedure_name": "  Total knee replacement (left) "})
    assert res.status_code == 200, res.text
    after = res.json()
    assert after["procedure_name"] == "Total knee replacement (left)"
    for field in ("procedure_type", "surgery_date", "discharge_date", "comorbidities", "full_name"):
        assert after[field] == before[field], field

    back = client.patch(url, headers=ctx["clinician"], json={"procedure_name": before["procedure_name"]})
    assert back.json() == before


def test_patch_finishes_pending_setup():
    client, TestSession, ctx = _setup()
    url = f"/patients/{ctx['patient_id']}"
    surgery = (date.today() - timedelta(days=2)).isoformat()
    discharge = (date.today() - timedelta(days=1)).isoformat()
    res = client.patch(url, headers=ctx["clinician"], json={
        "procedure_name": "Laparoscopic cholecystectomy", "procedure_type": "general",
        "surgery_date": surgery, "discharge_date": discharge, "date_of_birth": "1970-01-02",
        "comorbidities": ["Hypertension", " asthma ", "", "hypertension"],
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["procedure_type"] == "general"
    assert body["surgery_date"] == surgery and body["discharge_date"] == discharge
    assert body["comorbidities"] == ["Hypertension", "asthma"]
    with TestSession() as db:
        assert db.get(Patient, uuid.UUID(ctx["patient_id"])).date_of_birth == date(1970, 1, 2)

    cleared = client.patch(url, headers=ctx["clinician"], json={"discharge_date": None, "procedure_name": None})
    assert cleared.status_code == 200
    assert cleared.json()["discharge_date"] is None
    assert cleared.json()["procedure_name"] == "Laparoscopic cholecystectomy"


def test_patch_validation():
    client, _, ctx = _setup()
    url = f"/patients/{ctx['patient_id']}"
    assert client.patch(url, headers=ctx["clinician"], json={"procedure_name": "   "}).status_code == 422
    assert client.patch(url, headers=ctx["clinician"], json={"surgery_date": "not-a-date"}).status_code == 422
    # Fixed dates far from the seed's "surgery 3 days ago", so the check holds on any run date.
    bad_order = {"surgery_date": "2020-03-05", "discharge_date": "2020-03-01"}
    assert client.patch(url, headers=ctx["clinician"], json=bad_order).status_code == 422
    # Nothing from the rejected request was saved.
    assert client.get(url, headers=ctx["clinician"]).json()["surgery_date"] != "2020-03-05"


def test_patch_is_clinician_and_assignment_only():
    client, TestSession, ctx = _setup()
    url = f"/patients/{ctx['patient_id']}"
    assert client.patch(url, headers=ctx["patient"], json={"procedure_name": "x"}).status_code == 403
    assert client.patch(url, headers=_other_clinician_headers(TestSession), json={"procedure_name": "x"}).status_code == 404


# ---- POST /medications/{id}/logs status pending -----------------------------------

def test_pending_undoes_a_taken_dose():
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        med = db.scalar(select(Medication).where(Medication.name == "Aspirin"))
        med_id = str(med.id)
    when = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0).isoformat()
    url = f"/medications/{med_id}/logs"

    taken = client.post(url, headers=ctx["patient"], json={"scheduled_for": when, "status": "taken"})
    assert taken.status_code == 200, taken.text
    assert taken.json()["status"] == "taken" and taken.json()["responded_at"] is not None

    undo = client.post(url, headers=ctx["patient"], json={"scheduled_for": when, "status": "pending"})
    assert undo.status_code == 200, undo.text
    assert undo.json()["status"] == "pending" and undo.json()["responded_at"] is None
    assert undo.json()["id"] == taken.json()["id"]  # same row, kept

    with TestSession() as db:
        rows = db.scalars(select(MedicationLog).where(MedicationLog.medication_id == uuid.UUID(med_id))).all()
        assert len(rows) == 1 and rows[0].status == "pending"

    again = client.post(url, headers=ctx["patient"], json={"scheduled_for": when, "status": "skipped"})
    assert again.json()["status"] == "skipped" and again.json()["responded_at"] is not None


def test_unknown_dose_status_rejected():
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        med_id = str(db.scalar(select(Medication.id).limit(1)))
    res = client.post(f"/medications/{med_id}/logs", headers=ctx["patient"],
                      json={"scheduled_for": datetime.now(timezone.utc).isoformat(), "status": "missed"})
    assert res.status_code == 422


# ---- POST /chat source tag --------------------------------------------------------

class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def test_chat_source_voice_is_logged_as_event_only():
    client, _, ctx = _setup()
    handler = _ListHandler()
    chat_log = logging.getLogger("cloudcare.chat")
    chat_log.addHandler(handler)
    chat_log.setLevel(logging.INFO)
    try:
        res = client.post("/chat", headers=ctx["patient"],
                          json={"message": "When can I shower with the dressing?", "source": "voice"})
        default = client.post("/chat", headers=ctx["patient"], json={"message": "When can I shower?"})
    finally:
        chat_log.removeHandler(handler)
    assert res.status_code == 200, res.text
    assert res.json()["message"]["citations"][0]["section"] == "Wound care"
    assert default.status_code == 200
    assert handler.messages == ["chat.message source=voice", "chat.message source=chat"]
    assert client.post("/chat", headers=ctx["patient"], json={"message": "hi", "source": "sms"}).status_code == 422


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
