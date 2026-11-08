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
from app.models import ChatSession, Escalation, Patient, SymptomLog, User  # noqa: E402
from app.services.foggy import actions as actions_mod  # noqa: E402
from app.services.foggy import classify as classify_mod  # noqa: E402
from app.services.foggy import phrase  # noqa: E402
from app.services.foggy.classify import Classification  # noqa: E402

os.environ["LLM_PROVIDER"] = "none"  # nothing here may reach a real model
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


def _setup(classifications=None, plan_answer=None):
    from app.main import app

    _restore()
    _mock_model(classifications, plan_answer)
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

def test_checkin_flow_and_yes_is_not_consent():
    client, TestSession, ctx = _setup()
    with TestSession() as db:
        logs_before = len(db.scalars(select(SymptomLog).where(SymptomLog.patient_id == ctx["patient_id"])).all())
    esc_before = len(_escalations(TestSession, ctx))

    r = _say(client, ctx, "Can we do my recovery check-in?")
    assert r["route"] == "START_CHECKIN" and r["checkin"]["step"] == 1
    assert r["message"]["content"].endswith("What is your pain level from zero to ten?")
    r = _say(client, ctx, "Four.")
    assert r["checkin"]["step"] == 2 and r["checkin"]["answers"]["pain"] == 4
    assert r["message"]["content"] == "Have you taken your medicines as your care plan says?"
    r = _say(client, ctx, "Yes.")
    assert r["action_result"] is None and r["pending_action"] is None and r["escalated"] is False
    assert r["checkin"]["step"] == 3
    r = _say(client, ctx, "No.")
    assert r["checkin"]["step"] == 4
    assert r["message"]["content"] == "Have you had any falls since your last check-in?"  # seed has earlier check-ins
    r = _say(client, ctx, "No.")
    assert r["checkin"] == {"step": "done", "answers": {"pain": 4, "meds_taken": "yes", "numbness": "no", "fall": "no"}}
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


def test_checkin_keeps_volunteered_answers():
    client, _, ctx = _setup()
    r = _say(client, ctx, "Let's do a check-in. My pain is 3 and I took all my meds.")
    assert r["checkin"]["answers"] == {"pain": 3, "meds_taken": "yes"}
    assert r["checkin"]["step"] == 3
    assert r["message"]["content"].endswith("Have you had any new numbness, tingling, or change in skin color?")
    assert "pain level" not in r["message"]["content"]  # answered questions are not repeated


def test_checkin_unclear_meds_asks_which_medicine():
    client, _, ctx = _setup()
    _say(client, ctx, "check in please")
    _say(client, ctx, "6")
    r = _say(client, ctx, "I think so")
    assert r["checkin"]["answers"]["meds_taken"] == "unclear"
    assert r["message"]["content"] == "Which medicine did you miss or feel unsure about?"
    r = _say(client, ctx, "the aspirin")
    assert r["checkin"]["answers"]["meds_detail"] == "the aspirin" and r["checkin"]["step"] == 3
    assert "take" not in r["message"]["content"].lower()  # no missed-dose instructions


def test_checkin_non_answer_is_asked_again():
    client, _, ctx = _setup()
    _say(client, ctx, "check in please")
    assert _say(client, ctx, "hmm well")["message"]["content"] == "Please tell me a number from zero to ten."
    _say(client, ctx, "5")
    r = _say(client, ctx, "purple")
    assert r["message"]["content"] == "Have you taken all of your medicines as your care plan says, yes or no?"
    assert r["checkin"]["step"] == 2


def test_checkin_fall_interrupts_with_call_team():
    client, TestSession, ctx = _setup()
    _say(client, ctx, "Can we do my recovery check-in?")
    _say(client, ctx, "2")
    _say(client, ctx, "yes")
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
