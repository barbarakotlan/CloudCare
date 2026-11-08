"""Foggy policy v2: conversation state, consent, check-in, and enforcement.

The classifier and the plan phraser are mocked (no network); everything else is real:
in-memory SQLite seeded with the demo data, the FastAPI app, the router and actions.

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_foggy_state.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth, models, seed  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.models import ChatSession, Escalation, Medication, MedicationLog, Patient, SymptomLog, User  # noqa: E402
from app.services.foggy import actions as actions_mod  # noqa: E402
from app.services.foggy import classify as classify_mod  # noqa: E402
from app.services.foggy import doses as doses_mod  # noqa: E402
from app.services.foggy import phrase  # noqa: E402
from app.services.foggy.classify import Classification  # noqa: E402

os.environ["LLM_PROVIDER"] = "none"  # nothing here may reach a real model
# Jordan's doses: acetaminophen 06:00/14:00/22:00, aspirin 08:00/20:00, oxycodone as needed.
# Every test pins the check-in clock (local time of day in CHECKIN_TIMEZONE); 15:00 by default.
DEFAULT_NOW = "15:00"
seed.ensure_supabase_demo_users = lambda db: {}

_REAL_CLASSIFY = classify_mod.classify_message
_REAL_PLAN_ANSWER = phrase.plan_answer
_REAL_ESCALATION = actions_mod.Escalation


def _mock_model(classifications: dict | None = None, plan_answer=None):
    """Classifier returns the given Classification per message (None = rules only)."""
    table = classifications or {}
    classify_mod.classify_message = lambda message, chunks, history, state: table.get(message)
    phrase.plan_answer = plan_answer or (lambda message, chunks, history: None)


def _restore():
    classify_mod.classify_message = _REAL_CLASSIFY
    phrase.plan_answer = _REAL_PLAN_ANSWER
    actions_mod.Escalation = _REAL_ESCALATION
    os.environ.pop("CHECKIN_NOW_OVERRIDE", None)


def _setup(classifications=None, plan_answer=None, now=DEFAULT_NOW):
    from app.main import app

    _restore()
    _mock_model(classifications, plan_answer)
    os.environ["CHECKIN_NOW_OVERRIDE"] = now
    os.environ.pop("CHECKIN_TIMEZONE", None)
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
            "patient_id": patient.id,
        }
    return TestClient(app), TestSession, ctx


def _say(client, ctx, message, source="chat"):
    res = client.post("/chat", headers=ctx["patient"], json={"message": message, "source": source})
    assert res.status_code == 200, res.text
    return res.json()


def _escalations(TestSession, ctx, trigger=None):
    with TestSession() as db:
        q = select(Escalation).where(Escalation.patient_id == ctx["patient_id"])
        if trigger:
            q = q.where(Escalation.trigger_type == trigger)
        return db.scalars(q).all()


def _not_in_plan(topic="eating sushi"):
    return Classification(route="NOT_IN_PLAN", topic_kind="other", topic=topic, is_actual_report=False)


# ---- consent ----------------------------------------------------------------------

def test_not_in_plan_offers_and_sends_nothing():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    before = len(_escalations(TestSession, ctx))
    r = _say(client, ctx, "Can I eat sushi?")
    assert r["route"] == "NOT_IN_PLAN"
    assert r["message"]["content"] == ("Your care plan doesn't cover eating sushi. "
                                       "Would you like me to send a message to your care team?")
    assert r["offer_contact"] is True and r["escalated"] is False and r["action_result"] is None
    assert r["pending_action"]["kind"] == "message_care_team" and r["pending_action"]["recipient"] == "care_team"
    assert len(_escalations(TestSession, ctx)) == before


def test_consent_yes_without_a_care_team_queues_nothing():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    with TestSession() as db:  # a self-signed-up patient: no clinician assigned
        db.get(Patient, ctx["patient_id"]).clinician_id = None
        db.commit()
    before = len(_escalations(TestSession, ctx))
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "yes")
    assert r["action_result"]["status"] == "failed" and r["escalated"] is False
    assert r["message"]["content"] == phrase.NO_CARE_TEAM
    assert "queue" not in r["message"]["content"] and r["pending_action"] is None
    assert len(_escalations(TestSession, ctx)) == before


def test_consent_yes_sends_one_message():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "Yes, message my care team")
    assert r["route"] == "OPERATIONAL"
    assert r["action_result"]["status"] == "sent" and r["escalated"] is True
    assert r["message"]["content"] == "I've sent your message to your care team's queue."
    assert r["pending_action"] is None
    rows = _escalations(TestSession, ctx, "patient_request")
    assert len(rows) == 1 and rows[0].summary == "Can I eat sushi?" and rows[0].severity == "low"
    queue = client.get("/escalations", headers=ctx["clinician"]).json()
    assert any(e["trigger_type"] == "patient_request" and e["summary"] == "Can I eat sushi?" for e in queue)

    again = _say(client, ctx, "yes")  # nothing pending any more: no second message
    assert again["action_result"] is None and again["escalated"] is False
    assert len(_escalations(TestSession, ctx, "patient_request")) == 1


def test_consent_no_clears_offer():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "No thanks")
    assert r["message"]["content"].startswith("Okay, I won't send anything.")
    assert r["pending_action"] is None and r["action_result"] is None and r["escalated"] is False
    assert _say(client, ctx, "yes")["action_result"] is None
    assert _escalations(TestSession, ctx, "patient_request") == []


def test_consent_unclear_asks_once_then_drops():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    first = _say(client, ctx, "maybe")
    assert first["message"]["content"].startswith("Just to check")
    assert first["pending_action"] is not None and first["action_result"] is None
    second = _say(client, ctx, "hmm")
    assert second["pending_action"] is None and "won't send" in second["message"]["content"]
    assert _say(client, ctx, "yes")["action_result"] is None
    assert _escalations(TestSession, ctx, "patient_request") == []


def test_new_question_drops_offer():
    shower = {"content": "Your care plan says you may shower 48 hours after surgery with the waterproof dressing on.",
              "citations": [{"chunk_id": "x", "section": "Wound care"}], "answered_from_plan": True, "red_flag": False}
    client, TestSession, ctx = _setup(
        {"Can I eat sushi?": _not_in_plan(),
         "Can I shower?": Classification(route="ANSWER_FROM_PLAN", topic_kind="plan_question")},
        plan_answer=lambda m, c, h: shower)
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "Can I shower?")
    assert r["route"] == "ANSWER_FROM_PLAN" and r["pending_action"] is None
    assert r["message"]["citations"][0]["section"] == "Wound care"
    assert _say(client, ctx, "yes")["action_result"] is None  # the old offer is gone
    assert _escalations(TestSession, ctx, "patient_request") == []


def test_call_trigger_message_is_high_severity():
    client, TestSession, ctx = _setup()
    r = _say(client, ctx, "My calf is painful and swollen.")
    assert r["route"] == "CALL_SURGEON" and r["offer_contact"] is True and r["escalated"] is False
    r = _say(client, ctx, "yes please")
    assert r["action_result"]["status"] == "sent"
    assert "call your surgeon" in r["message"]["content"].lower()
    rows = _escalations(TestSession, ctx, "patient_request")
    assert len(rows) == 1 and rows[0].severity == "high"


def test_message_failure_is_reported_truthfully():
    from sqlalchemy import event
    from sqlalchemy.orm import Session as OrmSession

    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")

    def queue_down(session, flush_context, instances):  # the insert itself fails
        if any(isinstance(o, Escalation) and o.trigger_type == "patient_request" for o in session.new):
            raise RuntimeError("queue down")

    event.listen(OrmSession, "before_flush", queue_down)
    try:
        r = _say(client, ctx, "yes")
    finally:
        event.remove(OrmSession, "before_flush", queue_down)
    assert r["action_result"]["status"] == "failed" and r["escalated"] is False
    assert r["message"]["content"] == phrase.SEND_FAILED
    assert _escalations(TestSession, ctx, "patient_request") == []
    history = client.get("/chat/history", headers=ctx["patient"]).json()
    assert history[-2]["content"] == "yes" and history[-1]["content"] == phrase.SEND_FAILED  # turn still saved


# ---- check-in ----------------------------------------------------------------------

ACET_6 = "Did you take your acetaminophen one thousand milligrams at six this morning?"
ASPIRIN_8 = "Did you take your aspirin eighty-one milligrams at eight this morning?"
ACET_2 = "Did you take your acetaminophen one thousand milligrams at two this afternoon?"
OXY = "Did you need any oxycodone today?"
NUMBNESS = "Have you had any new numbness, tingling, or change in skin color?"


def _dose_logs(TestSession, ctx):
    """[(medicine name, local HH:MM, status, answered)] for Jordan's dose logs, by due time."""
    zone = doses_mod.local_zone()
    with TestSession() as db:
        rows = db.scalars(select(MedicationLog).join(Medication)
                          .where(Medication.patient_id == ctx["patient_id"])
                          .order_by(MedicationLog.scheduled_for)).all()
        return [(r.medication.name.lower(), doses_mod._as_utc(r.scheduled_for).astimezone(zone).strftime("%H:%M"),
                 r.status, r.responded_at is not None) for r in rows]


def _latest_checkin_text(TestSession, ctx):
    with TestSession() as db:
        return db.scalars(select(SymptomLog).where(SymptomLog.patient_id == ctx["patient_id"])
                          .order_by(SymptomLog.logged_at.desc())).first().free_text


def _assert_short(r):
    assert len(phrase.split_sentences(r["message"]["content"])) <= 2, r["message"]["content"]


def test_checkin_flow_and_yes_is_not_consent():
    client, TestSession, ctx = _setup(now="07:00")  # only the 6 AM acetaminophen is due
    with TestSession() as db:
        logs_before = len(db.scalars(select(SymptomLog).where(SymptomLog.patient_id == ctx["patient_id"])).all())
    esc_before = len(_escalations(TestSession, ctx))

    r = _say(client, ctx, "Can we do my recovery check-in?")
    assert r["route"] == "START_CHECKIN" and r["checkin"]["step"] == 1
    assert r["message"]["content"].endswith("What is your pain level from zero to ten?")
    r = _say(client, ctx, "Four.")
    assert r["checkin"]["step"] == 2 and r["checkin"]["answers"]["pain"] == 4
    assert r["message"]["content"] == ACET_6
    r = _say(client, ctx, "Yes.")
    assert r["action_result"] is None and r["pending_action"] is None and r["escalated"] is False
    assert r["checkin"]["step"] == 2 and r["message"]["content"] == OXY
    r = _say(client, ctx, "No.")
    assert r["checkin"]["step"] == 3 and r["message"]["content"] == NUMBNESS
    r = _say(client, ctx, "No.")
    assert r["checkin"]["step"] == 4
    assert r["message"]["content"] == "Have you had any falls since your last check-in?"  # seed has earlier check-ins
    r = _say(client, ctx, "No.")
    assert r["checkin"] == {"step": "done", "answers": {"pain": 4, "meds_taken": "yes", "numbness": "no", "fall": "no",
                                                        "as_needed": {"oxycodone": "no"}}, "substep": None}
    assert r["route"] == "OPERATIONAL" and r["message"]["content"].startswith("Thanks for checking in, Jordan.")

    with TestSession() as db:
        logs = db.scalars(select(SymptomLog).where(SymptomLog.patient_id == ctx["patient_id"])
                          .order_by(SymptomLog.logged_at.desc())).all()
        assert len(logs) == logs_before + 1
        assert logs[0].source == "chat" and logs[0].pain_level == 4
        session = db.get(ChatSession, ctx["patient_id"])
        assert session.checkin_state is None and session.pending_action is None
    assert len(_escalations(TestSession, ctx, "patient_request")) == 0
    assert len(_escalations(TestSession, ctx)) == esc_before  # low risk: nothing escalated
    assert _dose_logs(TestSession, ctx) == [("acetaminophen", "06:00", "taken", True)]


def test_checkin_keeps_volunteered_answers():
    client, _, ctx = _setup(now="05:00")  # no dose due yet
    r = _say(client, ctx, "Let's do a check-in. My pain is 3 and no falls.")
    assert r["checkin"]["answers"] == {"pain": 3, "meds_taken": "none_due", "fall": "no"}
    assert r["checkin"]["step"] == 3
    assert r["message"]["content"].endswith(NUMBNESS)
    assert "pain level" not in r["message"]["content"]  # answered questions are not repeated
    _assert_short(r)


# ---- check-in: one medicine question per dose due today -------------------------------------

def test_dose_loop_two_due_doses_writes_logs():
    client, TestSession, ctx = _setup(now="09:00")  # acetaminophen 6 AM and aspirin 8 AM are due
    _say(client, ctx, "Can we do my recovery check-in?")
    r = _say(client, ctx, "3")
    assert r["message"]["content"] == ACET_6 and r["checkin"]["step"] == 2
    sub = r["checkin"]["substep"]
    assert sub["name"] == "Acetaminophen" and sub["due_at"] and sub["medication_id"]
    r = _say(client, ctx, "yes")
    assert r["message"]["content"] == ASPIRIN_8 and r["checkin"]["substep"]["name"] == "Aspirin"
    assert r["checkin"]["step"] == 2
    r = _say(client, ctx, "yep")
    assert r["message"]["content"] == OXY
    assert r["checkin"]["substep"]["name"] == "Oxycodone" and r["checkin"]["substep"]["due_at"] is None
    r = _say(client, ctx, "no")
    assert r["message"]["content"] == NUMBNESS and r["checkin"]["step"] == 3 and r["checkin"]["substep"] is None
    _say(client, ctx, "no")
    r = _say(client, ctx, "no")
    assert r["checkin"]["step"] == "done" and r["checkin"]["answers"]["meds_taken"] == "yes"

    assert _dose_logs(TestSession, ctx) == [("acetaminophen", "06:00", "taken", True),
                                            ("aspirin", "08:00", "taken", True)]  # no row for oxycodone
    text = _latest_checkin_text(TestSession, ctx)
    assert "Taken: acetaminophen 6 AM, aspirin 8 AM" in text and "Oxycodone needed today: no" in text
    assert "Missed" not in text
    logs = client.get("/patients/me/medication-logs", headers=ctx["patient"]).json()
    assert sorted(entry["status"] for entry in logs) == ["taken", "taken"]


def test_dose_already_logged_is_not_asked():
    client, TestSession, ctx = _setup(now="09:00")
    meds = {m["name"]: m["id"] for m in client.get("/patients/me/medications", headers=ctx["patient"]).json()}
    six = doses_mod.now_utc().astimezone(doses_mod.local_zone()).replace(hour=6, minute=0, second=0, microsecond=0)
    res = client.post(f"/medications/{meds['Acetaminophen']}/logs", headers=ctx["patient"],
                      json={"scheduled_for": six.isoformat(), "status": "taken"})
    assert res.status_code == 200, res.text
    _say(client, ctx, "check in please")
    r = _say(client, ctx, "2")
    assert r["message"]["content"] == ASPIRIN_8  # the dashboard already has the 6 AM dose


def test_forgot_marks_dose_missed_without_advice():
    client, TestSession, ctx = _setup(now="09:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "2")
    _say(client, ctx, "yes")
    r = _say(client, ctx, "I forgot")
    assert r["message"]["content"] == f"Okay, I've noted that one as missed. {OXY}"
    for advice in ("take it", "double", "next dose", "skip", "later"):
        assert advice not in r["message"]["content"].lower()
    assert r["pending_action"] is None and r["escalated"] is False
    assert _dose_logs(TestSession, ctx)[-1] == ("aspirin", "08:00", "skipped", True)
    for msg in ("no", "no", "no"):
        r = _say(client, ctx, msg)
    assert r["checkin"]["step"] == "done"
    assert r["checkin"]["answers"]["meds_taken"] == "no"
    assert r["checkin"]["answers"]["missed_doses"] == ["aspirin 8 AM"]
    assert "Missed: aspirin 8 AM" in _latest_checkin_text(TestSession, ctx)


def test_missed_word_marks_dose_skipped():
    client, TestSession, ctx = _setup(now="07:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "2")
    r = _say(client, ctx, "missed it")
    assert r["message"]["content"].startswith("Okay, I've noted that one as missed.")
    assert _dose_logs(TestSession, ctx) == [("acetaminophen", "06:00", "skipped", True)]


def test_unclear_dose_answer_is_asked_once_then_left_blank():
    client, TestSession, ctx = _setup(now="09:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "2")
    r = _say(client, ctx, "I think so")
    assert r["message"]["content"] == "Just to check, did you take your acetaminophen at six this morning, yes or no?"
    assert r["checkin"]["substep"]["name"] == "Acetaminophen"
    r = _say(client, ctx, "not sure")
    assert r["message"]["content"] == f"Okay, I'll leave that one blank. {ASPIRIN_8}"
    assert _dose_logs(TestSession, ctx) == []  # nothing recorded for the unclear dose
    r = _say(client, ctx, "purple")  # a reply that answers nothing counts as unclear too
    assert r["message"]["content"].startswith("Just to check, did you take your aspirin")
    _say(client, ctx, "yes")
    assert _dose_logs(TestSession, ctx) == [("aspirin", "08:00", "taken", True)]


def test_no_due_doses_skips_the_medicine_step():
    client, TestSession, ctx = _setup(now="05:30")
    _say(client, ctx, "Can we do my recovery check-in?")
    r = _say(client, ctx, "1")
    assert r["message"]["content"] == f"{phrase.NO_DOSES_DUE} {NUMBNESS}"
    assert r["checkin"]["step"] == 3 and r["checkin"]["answers"]["meds_taken"] == "none_due"
    assert OXY not in r["message"]["content"]
    _say(client, ctx, "no")
    r = _say(client, ctx, "no")
    assert r["checkin"]["step"] == "done"
    assert _dose_logs(TestSession, ctx) == []
    assert "No medicine doses were due yet today" in _latest_checkin_text(TestSession, ctx)


def test_volunteered_took_everything_marks_all_due_doses():
    client, TestSession, ctx = _setup(now="15:00")
    r = _say(client, ctx, "Let's do a check-in. My pain is 3 and I took everything this morning.")
    assert r["checkin"]["answers"] == {"pain": 3}
    assert r["message"]["content"].endswith(OXY) and r["checkin"]["step"] == 2  # only the as-needed question left
    _assert_short(r)
    assert _dose_logs(TestSession, ctx) == [("acetaminophen", "06:00", "taken", True),
                                            ("aspirin", "08:00", "taken", True),
                                            ("acetaminophen", "14:00", "taken", True)]


def test_model_meds_taken_flag_marks_all_due_doses():
    msg = "Morning pills all went down fine, pain is about a 2"
    client, TestSession, ctx = _setup(
        {msg: Classification(route="START_CHECKIN", topic_kind="checkin_request",
                             checkin_answers={"pain": 2, "meds_taken": "yes"})}, now="09:00")
    r = _say(client, ctx, msg)
    assert r["message"]["content"].endswith(OXY)
    assert [row[2] for row in _dose_logs(TestSession, ctx)] == ["taken", "taken"]


def test_named_medicine_answers_that_medicine():
    client, TestSession, ctx = _setup(now="15:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "4")
    r = _say(client, ctx, "I took the acetaminophen but skipped the aspirin")
    assert r["message"]["content"] == f"Okay, I've noted that one as missed. {ACET_2}"
    assert _dose_logs(TestSession, ctx) == [("acetaminophen", "06:00", "taken", True),
                                            ("aspirin", "08:00", "skipped", True)]


def test_model_medication_mentions_are_used():
    msg = "the tylenol went down fine this morning"
    client, TestSession, ctx = _setup(
        {msg: Classification(route="OPERATIONAL", topic_kind="checkin_answer",
                             medication_mentions=[{"name": "Tylenol", "taken": True}])}, now="07:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "3")
    r = _say(client, ctx, msg)
    assert r["message"]["content"] == OXY
    assert _dose_logs(TestSession, ctx) == [("acetaminophen", "06:00", "taken", True)]


def test_as_needed_answer_goes_to_checkin_text_only():
    client, TestSession, ctx = _setup(now="07:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "5")
    _say(client, ctx, "yes")
    r = _say(client, ctx, "yes, one last night")
    assert r["message"]["content"] == NUMBNESS
    for msg in ("no", "no"):
        r = _say(client, ctx, msg)
    assert r["checkin"]["answers"]["as_needed"] == {"oxycodone": "yes"}
    assert "Oxycodone needed today: yes" in _latest_checkin_text(TestSession, ctx)
    assert [row[0] for row in _dose_logs(TestSession, ctx)] == ["acetaminophen"]  # no oxycodone row


def test_missed_dose_question_in_loop_offers_contact():
    client, TestSession, ctx = _setup(now="09:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "2")
    _say(client, ctx, "yes")
    r = _say(client, ctx, "I missed my aspirin this morning, should I take it now?")
    assert r["route"] == "NOT_IN_PLAN" and r["offer_contact"] is True
    assert r["message"]["content"].startswith("Your care plan doesn't say what to do after a missed dose.")
    assert _dose_logs(TestSession, ctx)[-1] == ("aspirin", "08:00", "skipped", True)
    r = _say(client, ctx, "no thanks")
    assert r["message"]["content"] == f"Okay, I won't send anything. {OXY}"  # the check-in picks up again


def test_emergency_interrupts_dose_loop():
    client, TestSession, ctx = _setup(now="09:00")
    _say(client, ctx, "check in please")
    _say(client, ctx, "2")
    r = _say(client, ctx, "I can't breathe")
    assert r["route"] == "EMERGENCY_911" and r["checkin"] is None
    assert _dose_logs(TestSession, ctx) == []


def test_generic_medicine_question_without_a_medication_list():
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        for med in db.scalars(select(Medication).where(Medication.patient_id == ctx["patient_id"])):
            db.delete(med)
        db.commit()
    _say(client, ctx, "check in please")
    r = _say(client, ctx, "6")
    assert r["message"]["content"] == "Have you taken your medicines as your care plan says?"
    r = _say(client, ctx, "I think so")
    assert r["checkin"]["answers"]["meds_taken"] == "unclear"
    assert r["message"]["content"] == "Which medicine did you miss or feel unsure about?"
    r = _say(client, ctx, "the aspirin")
    assert r["checkin"]["answers"]["meds_detail"] == "the aspirin" and r["checkin"]["step"] == 3
    assert "take" not in r["message"]["content"].lower()  # no missed-dose instructions


def test_speech_friendly_dose_wording():
    assert doses_mod.spoken_time(6, 0) == "six this morning"
    assert doses_mod.spoken_time(14, 0) == "two this afternoon"
    assert doses_mod.spoken_time(20, 0) == "eight tonight"
    assert doses_mod.spoken_time(22, 0) == "ten tonight"
    assert doses_mod.spoken_time(12, 0) == "noon"
    assert doses_mod.spoken_time(18, 30) == "six thirty this evening"
    assert doses_mod.spoken_dosage("1000 mg") == "one thousand milligrams"
    assert doses_mod.spoken_dosage("81 mg") == "eighty-one milligrams"
    assert doses_mod.spoken_dosage("2.5 mg") == "two point five milligrams"
    assert doses_mod.spoken_dosage("1 tablet") == "one tablet"
    assert doses_mod.short_time(8, 0) == "8 AM" and doses_mod.short_time(14, 0) == "2 PM"
    assert doses_mod.mentions("No, I didn't take the aspirin", ["Aspirin"]) == [{"name": "Aspirin", "taken": False}]
    assert doses_mod.mentions("took my Tylenol and the aspirin", ["Acetaminophen", "Aspirin"]) == [
        {"name": "Acetaminophen", "taken": True}, {"name": "Aspirin", "taken": True}]
    assert doses_mod.mentions("Can I take my aspirin later?", ["Aspirin"]) == []


def test_checkin_non_answer_is_asked_again():
    client, _, ctx = _setup()
    _say(client, ctx, "check in please")
    assert _say(client, ctx, "hmm well")["message"]["content"] == "Please tell me a number from zero to ten."
    r = _say(client, ctx, "5")
    assert r["checkin"]["step"] == 2 and r["message"]["content"] == ACET_6


def test_checkin_fall_interrupts_with_call_team():
    client, TestSession, ctx = _setup(now="05:00")  # nothing due: pain, then numbness, then falls
    _say(client, ctx, "Can we do my recovery check-in?")
    _say(client, ctx, "2")
    _say(client, ctx, "no")
    r = _say(client, ctx, "Yes, I fell in the bathroom")
    assert r["route"] == "CALL_SURGEON" and r["offer_contact"] is True
    assert r["checkin"]["step"] == "done" and r["checkin"]["answers"]["fall"] == "yes"
    assert _escalations(TestSession, ctx, "patient_request") == []  # offered, not sent


def test_emergency_interrupts_checkin():
    client, TestSession, ctx = _setup()
    _say(client, ctx, "Can we do my recovery check-in?")
    r = _say(client, ctx, "I can't breathe")
    assert r["route"] == "EMERGENCY_911"
    assert r["message"]["content"] == "Call 911 now. I can't place emergency calls."
    assert r["checkin"] is None and r["pending_action"] is None and r["escalated"] is True
    assert r["message"]["red_flag"] is True
    rows = _escalations(TestSession, ctx, "red_flag")
    assert len(rows) == 1 and rows[0].severity == "emergency"
    with TestSession() as db:
        assert db.get(ChatSession, ctx["patient_id"]).checkin_state is None


def test_emergency_beats_pending_offer():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "yes, and my chest hurts")
    assert r["route"] == "EMERGENCY_911" and r["action_result"] is None
    assert _escalations(TestSession, ctx, "patient_request") == []


# ---- emergency and call-trigger recognition ----------------------------------------------

def test_denial_is_not_emergency():
    client, TestSession, ctx = _setup()
    r = _say(client, ctx, "No chest pain and no trouble breathing. How often do I change my dressing?")
    assert r["route"] != "EMERGENCY_911" and r["escalated"] is False
    assert _escalations(TestSession, ctx, "red_flag") == []


def test_hypothetical_is_not_emergency():
    client, TestSession, ctx = _setup()
    r = _say(client, ctx, "What should I do if I get chest pain?")
    assert r["route"] == "ANSWER_FROM_PLAN" and "911" in r["message"]["content"]
    assert _escalations(TestSession, ctx, "red_flag") == []


def test_model_can_mark_a_quotation_as_not_a_report():
    quote = "My friend said chest pain is common after surgery, is that true?"
    client, TestSession, ctx = _setup({quote: Classification(route="NOT_IN_PLAN", topic_kind="other_medical",
                                                             is_actual_report=False)})
    r = _say(client, ctx, quote)
    assert r["route"] == "NOT_IN_PLAN"
    assert _escalations(TestSession, ctx, "red_flag") == []


def test_model_cannot_soften_a_report():
    msg = "I feel fine but I passed out an hour ago"
    client, TestSession, ctx = _setup({msg: Classification(route="EMERGENCY_911", topic_kind="symptom_report",
                                                           is_actual_report=True, symptoms=["fainting"])})
    r = _say(client, ctx, msg)
    assert r["message"]["content"] == "Call 911 now. I can't place emergency calls."
    assert len(_escalations(TestSession, ctx, "red_flag")) == 1


def test_fever_boundary():
    client, _, ctx = _setup()
    assert _say(client, ctx, "My temperature is 101.5")["route"] != "CALL_SURGEON"
    assert _say(client, ctx, "My temperature is 102")["route"] == "CALL_SURGEON"
    assert _say(client, ctx, "I have a fever of 101.6 F")["route"] == "CALL_SURGEON"


def test_fever_boundary_with_model_saying_call():
    msg = "My temperature is 101.5 degrees"
    client, _, ctx = _setup({msg: Classification(route="CALL_SURGEON", topic_kind="symptom_report",
                                                 is_actual_report=True, symptoms=["fever"], temperature_f=101.5)})
    assert _say(client, ctx, msg)["route"] != "CALL_SURGEON"


def test_other_person_is_not_in_plan():
    msg = "My husband's calf is swollen, what should he do?"
    client, _, ctx = _setup({msg: Classification(route="CALL_SURGEON", topic_kind="family_member",
                                                 is_actual_report=True, symptoms=["calf_pain_swelling"],
                                                 about_other_person=True)})
    r = _say(client, ctx, msg)
    assert r["route"] == "NOT_IN_PLAN" and "your husband" in r["message"]["content"]


def test_identity_answer():
    client, _, ctx = _setup()
    r = _say(client, ctx, "Are you a doctor?")
    assert r["route"] == "OPERATIONAL"
    assert r["message"]["content"] == ("I'm an AI recovery helper, not a doctor or nurse. "
                                       "I can help explain your surgeon's care plan.")


def test_call_request_explains_real_capability():
    client, TestSession, ctx = _setup()
    r = _say(client, ctx, "Can you call my surgeon for me?")
    assert r["route"] == "OPERATIONAL" and "can't place phone calls" in r["message"]["content"]
    assert r["offer_contact"] is True and _escalations(TestSession, ctx, "patient_request") == []


# ---- social turns: acknowledgments, thanks, greetings, goodbyes, well-being ------------------

def _replies(kind):
    return {o.format(n=", Jordan", hi=" Jordan") for o in phrase.SOCIAL_REPLIES[kind]}


def _assert_social(r, kind):
    assert r["route"] == "OPERATIONAL", r
    assert r["message"]["content"] in _replies(kind), r["message"]["content"]
    assert r["offer_contact"] is False and r["pending_action"] is None
    assert r["action_result"] is None and r["escalated"] is False and r["checkin"] is None
    assert r["message"]["answered_from_plan"] is None and r["message"]["red_flag"] is False


def test_acknowledgment_is_not_out_of_scope():
    client, TestSession, ctx = _setup()
    before = len(_escalations(TestSession, ctx))
    for msg in ("Will do", "Got it.", "sounds good", "No problem!", "yes please"):
        _assert_social(_say(client, ctx, msg), "acknowledgment")
    assert len(_escalations(TestSession, ctx)) == before
    with TestSession() as db:
        session = db.get(ChatSession, ctx["patient_id"])
        assert session.pending_action is None and session.checkin_state is None


def test_thanks_greeting_goodbye_wellbeing():
    client, TestSession, ctx = _setup()
    before = len(_escalations(TestSession, ctx))
    _assert_social(_say(client, ctx, "Thanks Foggy"), "thanks")
    _assert_social(_say(client, ctx, "I appreciate it!"), "thanks")
    _assert_social(_say(client, ctx, "Hello?"), "greeting")
    _assert_social(_say(client, ctx, "hey Foggy"), "greeting")
    _assert_social(_say(client, ctx, "I'm doing fine today"), "wellbeing")
    _assert_social(_say(client, ctx, "feeling better today"), "wellbeing")
    _assert_social(_say(client, ctx, "had a good night"), "wellbeing")
    _assert_social(_say(client, ctx, "Okay, that's all for today, bye!"), "goodbye")
    r = _say(client, ctx, "goodnight")
    assert r["route"] == "OPERATIONAL" and r["message"]["content"] in _replies("goodnight")
    assert len(_escalations(TestSession, ctx)) == before


def test_social_replies_vary():
    client, _, ctx = _setup()
    first = _say(client, ctx, "thanks")["message"]["content"]
    second = _say(client, ctx, "thanks")["message"]["content"]
    assert first != second and {first, second} <= _replies("thanks")
    assert all(len(phrase.split_sentences(o)) <= 2 for kind in phrase.SOCIAL_REPLIES for o in _replies(kind))


def test_social_skips_the_model():
    client, _, ctx = _setup()
    calls = []
    classify_mod.classify_message = lambda message, *rest: calls.append(message) or _not_in_plan()
    _assert_social(_say(client, ctx, "Will do"), "acknowledgment")  # a model "not in plan" can't override it
    assert calls == []
    assert _say(client, ctx, "Can I eat sushi?")["route"] == "NOT_IN_PLAN"
    assert calls == ["Can I eat sushi?"]


def test_wellbeing_with_a_symptom_is_not_social():
    client, TestSession, ctx = _setup()
    r = _say(client, ctx, "I'm fine but I can't breathe")
    assert r["route"] == "EMERGENCY_911"
    assert r["message"]["content"] == "Call 911 now. I can't place emergency calls."
    assert len(_escalations(TestSession, ctx, "red_flag")) == 1
    r = _say(client, ctx, "I'm doing fine but my calf is swollen")
    assert r["route"] == "CALL_SURGEON" and r["offer_contact"] is True


def test_model_wellbeing_label_needs_no_symptom():
    calm = "Honestly I'm feeling a whole lot more like myself than yesterday"
    sore = "Doing alright overall, the knee is sore when I bend it though"
    label = Classification(route="OPERATIONAL", topic_kind="other", operational_kind="wellbeing")
    client, _, ctx = _setup({calm: label, sore: label})
    _assert_social(_say(client, ctx, calm), "wellbeing")
    assert _say(client, ctx, sore)["message"]["content"] not in _replies("wellbeing")


def test_model_acknowledgment_label_is_not_out_of_scope():
    msg = "alrighty, I'll keep that in mind"
    client, _, ctx = _setup({msg: Classification(route="OPERATIONAL", topic_kind="other",
                                                 operational_kind="acknowledgment")})
    _assert_social(_say(client, ctx, msg), "acknowledgment")


def test_acknowledgment_with_pending_offer_asks_again_once():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    first = _say(client, ctx, "Will do")
    assert first["message"]["content"].startswith("Just to check")
    assert first["pending_action"] is not None and first["action_result"] is None
    second = _say(client, ctx, "Okay, got it")
    assert second["pending_action"] is None and "won't send" in second["message"]["content"]
    assert _say(client, ctx, "yes")["action_result"] is None
    assert _escalations(TestSession, ctx, "patient_request") == []


def test_okay_and_thanks_are_not_consent():
    for reply in ("okay", "Thanks!", "sounds good"):
        client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
        _say(client, ctx, "Can I eat sushi?")
        r = _say(client, ctx, reply)
        assert r["action_result"] is None and r["message"]["content"].startswith("Just to check"), reply
        assert _escalations(TestSession, ctx, "patient_request") == []


def test_aside_keeps_the_offer_pending():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "hold on")
    assert r["route"] == "OPERATIONAL" and r["message"]["content"] == phrase.ASIDE
    assert r["pending_action"] is not None and r["action_result"] is None
    r = _say(client, ctx, "yes")
    assert r["action_result"]["status"] == "sent"
    assert len(_escalations(TestSession, ctx, "patient_request")) == 1


def test_aside_keeps_the_checkin():
    client, _, ctx = _setup()
    _say(client, ctx, "Can we do my recovery check-in?")
    r = _say(client, ctx, "one sec")
    assert r["message"]["content"] == phrase.ASIDE
    r = _say(client, ctx, "3")
    assert r["checkin"]["step"] == 2 and r["checkin"]["answers"]["pain"] == 3


def test_goodbye_with_pending_offer_sends_nothing():
    client, TestSession, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?")
    r = _say(client, ctx, "bye")
    assert r["pending_action"] is None and r["action_result"] is None
    assert r["message"]["content"] == "Okay, I won't send anything. Take care, Jordan."
    assert _escalations(TestSession, ctx, "patient_request") == []


# ---- enforcement -----------------------------------------------------------------------------

def test_two_sentence_cap():
    long = {"content": "Your care plan says to shower after 48 hours. Use the waterproof dressing. Do not soak. "
                       "Change the dressing every 2 days.",
            "citations": [{"chunk_id": "x", "section": "Wound care"}], "answered_from_plan": True, "red_flag": False}
    msg = "Tell me about showering"
    client, _, ctx = _setup({msg: Classification(route="ANSWER_FROM_PLAN", topic_kind="plan_question")},
                            plan_answer=lambda m, c, h: long)
    r = _say(client, ctx, msg)
    assert r["message"]["content"] == "Your care plan says to shower after 48 hours. Use the waterproof dressing."
    assert phrase.enforce("A fever over 101.5 F. Call Dr. Patel now. Third. Fourth.", "CALL_SURGEON") == \
        "A fever over 101.5 F. Call Dr. Patel now."


def test_911_digits_and_forced_emergency_wording():
    assert phrase.enforce("Your plan says call nine one one for chest pain.", "ANSWER_FROM_PLAN") == \
        "Your plan says call 911 for chest pain."
    assert phrase.enforce("Call 9-1-1 for trouble breathing.", "ANSWER_FROM_PLAN") == "Call 911 for trouble breathing."
    assert phrase.enforce("Please consider getting help. Your team was notified.", "EMERGENCY_911") == \
        "Call 911 now. I can't place emergency calls."
    assert phrase.enforce("**Bold** text", "OPERATIONAL") == "Bold text"


# ---- duplicate prevention --------------------------------------------------------------------

def test_actions_never_duplicate_within_a_turn():
    _, TestSession, ctx = _setup()
    with TestSession() as db:
        patient = db.get(Patient, ctx["patient_id"])
        acts = actions_mod.TurnActions(db, patient, None)
        pending = {"kind": "message_care_team", "recipient": "care_team", "reason": "r", "origin_route": "NOT_IN_PLAN",
                   "patient_words": "Can I eat sushi?"}
        first = acts.message_care_team(pending, "yes")
        second = acts.message_care_team(pending, "yes")
        assert first == second and first["status"] == "sent"
        assert acts.emergency_alert("I can't breathe") is True
        assert acts.emergency_alert("I can't breathe") is False
        db.commit()
    assert len(_escalations(TestSession, ctx, "patient_request")) == 1
    assert len(_escalations(TestSession, ctx, "red_flag")) == 1


def test_no_agreement_no_action():
    _, TestSession, ctx = _setup()
    with TestSession() as db:
        acts = actions_mod.TurnActions(db, db.get(Patient, ctx["patient_id"]), None)
        result = acts.message_care_team({"kind": "message_care_team", "recipient": "care_team"}, "unclear")
        assert result["status"] == "failed"
        db.commit()
    assert _escalations(TestSession, ctx, "patient_request") == []


def test_repeated_emergency_message_is_not_duplicated():
    client, TestSession, ctx = _setup()
    first = _say(client, ctx, "I can't catch my breath.")
    second = _say(client, ctx, "I can't catch my breath.")
    assert first["escalated"] is True and second["escalated"] is False
    assert second["message"]["content"] == "Call 911 now. I can't place emergency calls."  # wording never changes
    assert len(_escalations(TestSession, ctx, "red_flag")) == 1


# ---- endpoints ------------------------------------------------------------------------------

def test_capabilities_endpoint():
    client, _, ctx = _setup()
    res = client.get("/chat/capabilities", headers=ctx["patient"])
    assert res.status_code == 200
    assert res.json() == {"message_care_team": True, "call_care_team": False, "emergency_call_assist": False,
                          "simulated": False}
    assert client.get("/chat/capabilities").status_code == 401


def test_history_has_routes_and_voice_shares_state():
    client, _, ctx = _setup({"Can I eat sushi?": _not_in_plan()})
    _say(client, ctx, "Can I eat sushi?", source="chat")
    r = _say(client, ctx, "yes", source="voice")  # the voice agent answers the chat offer
    assert r["action_result"]["status"] == "sent"
    history = client.get("/chat/history", headers=ctx["patient"]).json()
    assistant = [m for m in history if m["role"] == "assistant"]
    assert [m["route"] for m in assistant[-2:]] == ["NOT_IN_PLAN", "OPERATIONAL"]
    assert [m["role"] for m in history[-4:]] == ["patient", "assistant", "patient", "assistant"]


# ---- voice: off-track turns steer back to the check-in ----------------------------------------

STEER_LEADS = tuple(s.split("{")[0].strip() for s in phrase.STEER_LEADS)


def _steer_lead(text):
    return next((lead for lead in STEER_LEADS if lead in text), None)


def _assert_steer(r, question):
    """Two sentences at most, the last one a steer that asks `question` again."""
    _assert_short(r)
    last = phrase.split_sentences(r["message"]["content"])[-1]
    assert _steer_lead(last) and last.endswith(question), r["message"]["content"]


def test_voice_off_topic_during_checkin_steers_back():
    client, TestSession, ctx = _setup(now="05:00")  # no dose due: pain, numbness, falls
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    r = _say(client, ctx, "What's the weather like?", source="voice")
    assert r["route"] == "NOT_IN_PLAN"
    first, _ = phrase.split_sentences(r["message"]["content"])
    assert first in phrase.OFF_TOPIC_VOICE  # one friendly line, no "doesn't cover that"
    _assert_steer(r, "what's your pain from zero to ten?")
    assert r["offer_contact"] is False and r["pending_action"] is None and r["escalated"] is False
    assert r["checkin"]["step"] == 1

    again = _say(client, ctx, "Who won the game?", source="voice")
    _assert_steer(again, "what's your pain from zero to ten?")
    assert _steer_lead(again["message"]["content"]) != _steer_lead(r["message"]["content"])  # never the same twice
    assert phrase.split_sentences(again["message"]["content"])[0] != first

    r = _say(client, ctx, "3", source="voice")
    assert r["checkin"]["step"] == 3 and r["checkin"]["answers"]["pain"] == 3
    assert _escalations(TestSession, ctx, "patient_request") == []


def test_chat_off_topic_during_checkin_is_unchanged():
    client, _, ctx = _setup(now="05:00")
    _say(client, ctx, "Can we do my recovery check-in?")
    r = _say(client, ctx, "What's the weather like?")
    assert r["route"] == "NOT_IN_PLAN" and r["offer_contact"] is True
    assert r["message"]["content"] == ("I can only help with your recovery care plan. "
                                       "Would you like me to send a message to your care team?")
    assert _steer_lead(r["message"]["content"]) is None


def test_voice_steer_never_repeats_back_to_back():
    client, _, ctx = _setup(now="05:00")
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    leads = []
    for msg in ("What's the weather like?", "Who won the game?", "Tell me a joke.", "What's the score?",
                "What's the news today?"):
        r = _say(client, ctx, msg, source="voice")
        _assert_steer(r, "what's your pain from zero to ten?")
        leads.append(_steer_lead(r["message"]["content"]))
    assert all(a != b for a, b in zip(leads, leads[1:])), leads


def test_voice_off_topic_without_question_mark_is_not_a_bad_answer():
    client, _, ctx = _setup(now="07:00")  # the 6 AM acetaminophen is due
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    assert _say(client, ctx, "4", source="voice")["message"]["content"] == ACET_6
    r = _say(client, ctx, "who won the game", source="voice")
    _assert_steer(r, "did you take your acetaminophen at six this morning?")
    assert r["checkin"]["step"] == 2 and r["checkin"]["substep"]["name"] == "Acetaminophen"

    client, _, ctx = _setup(now="07:00")  # chat keeps asking the dose question again
    _say(client, ctx, "Can we do my recovery check-in?")
    _say(client, ctx, "4")
    r = _say(client, ctx, "who won the game")
    assert r["route"] == "START_CHECKIN" and _steer_lead(r["message"]["content"]) is None


def test_voice_not_in_plan_keeps_the_offer_and_resumes_after_it():
    client, TestSession, ctx = _setup(now="05:00")
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    r = _say(client, ctx, "Can I take ibuprofen?", source="voice")
    assert r["route"] == "NOT_IN_PLAN" and r["offer_contact"] is True
    assert r["message"]["content"].endswith(phrase.OFFER)  # the offer needs the second sentence: no steer yet
    assert _steer_lead(r["message"]["content"]) is None
    _assert_short(r)
    r = _say(client, ctx, "yes", source="voice")
    assert r["action_result"]["status"] == "sent"
    assert r["message"]["content"] == f"{phrase.SENT} What is your pain level from zero to ten?"
    assert len(_escalations(TestSession, ctx, "patient_request")) == 1


def test_voice_identity_and_capability_during_checkin():
    client, _, ctx = _setup(now="05:00")
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    r = _say(client, ctx, "Are you a robot?", source="voice")
    assert r["route"] == "OPERATIONAL"
    assert r["message"]["content"].startswith("I'm an AI recovery helper, not a doctor or nurse.")
    _assert_steer(r, "what's your pain from zero to ten?")

    r = _say(client, ctx, "Can you call my surgeon for me?", source="voice")
    assert r["offer_contact"] is True and r["message"]["content"] == phrase.CAPABILITY  # offer first, steer later

    client, _, ctx = _setup(now="05:00")  # chat: the full identity answer, no steer
    _say(client, ctx, "Can we do my recovery check-in?")
    r = _say(client, ctx, "Are you a robot?")
    assert r["message"]["content"] == phrase.IDENTITY


def test_voice_off_topic_without_checkin_invites_a_recovery_question():
    client, _, ctx = _setup()
    r = _say(client, ctx, "Who won the game last night?", source="voice")
    assert r["route"] == "NOT_IN_PLAN" and r["offer_contact"] is False and r["checkin"] is None
    first, second = phrase.split_sentences(r["message"]["content"])
    assert first in phrase.OFF_TOPIC_VOICE and second in phrase.WRAP_UP_VOICE
    r = _say(client, ctx, "Who won the game last night?")  # chat: scope line and the offer, as before
    assert r["offer_contact"] is True and r["message"]["content"].endswith(phrase.OFFER)


def test_voice_checkin_request_mid_checkin_picks_up_where_it_stopped():
    client, _, ctx = _setup(now="05:00")
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    _say(client, ctx, "2", source="voice")
    r = _say(client, ctx, "Let's do my check-in.", source="voice")
    assert r["route"] == "START_CHECKIN" and r["checkin"]["step"] == 3
    assert r["message"]["content"] == f"Let's keep going with your check-in. {NUMBNESS}"


def test_voice_checkin_close_invites_anything_else():
    client, _, ctx = _setup(now="05:00")
    _say(client, ctx, "Can we do my recovery check-in?", source="voice")
    _say(client, ctx, "2", source="voice")
    _say(client, ctx, "no", source="voice")
    r = _say(client, ctx, "no", source="voice")
    assert r["checkin"]["step"] == "done" and r["route"] == "OPERATIONAL"
    assert r["message"]["content"] == ("Thanks for checking in, Jordan, I saved your answers. "
                                       "Anything else about your recovery before we wrap up?")
    _assert_short(r)


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
        finally:
            _restore()
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
