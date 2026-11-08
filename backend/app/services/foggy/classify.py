"""Gemini (or any configured provider) classifier: reads one patient message and returns
structured facts about it. It never writes the reply and never decides an action; the
router applies the policy's priority order and state rules to what it returns.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.services import ai_service

log = logging.getLogger("cloudcare.foggy")

ROUTES = ("EMERGENCY_911", "CALL_SURGEON", "REFUSE_DOSE_CHANGE", "START_CHECKIN", "NOT_IN_PLAN",
          "ANSWER_FROM_PLAN", "OPERATIONAL")
SYMPTOMS = ("chest_pain", "trouble_breathing", "heavy_bleeding", "fainting", "call_911_request", "self_harm",
            "fever", "redness_or_drainage", "calf_pain_or_swelling", "uncontrolled_pain", "fall",
            "numbness_tingling_color", "other")
TOPIC_KINDS = ("plan_question", "missed_dose", "unlisted_medication", "dose_interval_or_max", "alcohol_or_cannabis",
               "second_opinion", "work_or_travel", "family_member", "non_medical", "feelings", "other_medical",
               "identity", "capability", "greeting", "thanks", "consent_answer", "checkin_answer", "dose_change",
               "symptom_report", "checkin_request", "other")
OPERATIONAL_KINDS = ("acknowledgment", "thanks", "greeting", "goodbye", "wellbeing", "identity", "capability", "none")

# Router names for classifier symptom labels.
SYMPTOM_TO_SIGN = {
    "chest_pain": "chest_pain", "trouble_breathing": "trouble_breathing", "heavy_bleeding": "heavy_bleeding",
    "fainting": "fainting", "call_911_request": "call_911", "self_harm": "self_harm",
    "fever": "fever", "redness_or_drainage": "redness_drainage", "calf_pain_or_swelling": "calf_pain_swelling",
    "uncontrolled_pain": "uncontrolled_pain", "fall": "fall", "numbness_tingling_color": "numbness_tingling_color",
}

_YN = {"type": "string", "enum": ["yes", "no", "not_given"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "route": {"type": "string", "enum": list(ROUTES)},
        "operational_kind": {"type": "string", "enum": list(OPERATIONAL_KINDS)},
        "topic_kind": {"type": "string", "enum": list(TOPIC_KINDS)},
        "topic": {"type": "string"},
        "is_actual_report": {"type": "boolean"},
        "symptoms": {"type": "array", "items": {"type": "string", "enum": list(SYMPTOMS)}},
        "temperature_f": {"type": "number"},
        "is_consent": {"type": "string", "enum": ["yes", "no", "unclear", "n/a"]},
        "checkin_answers": {
            "type": "object",
            "properties": {
                "pain": {"type": "integer"},
                "meds_taken": {"type": "string", "enum": ["yes", "no", "unclear", "not_given"]},
                "numbness": _YN,
                "fall": _YN,
            },
            "required": ["pain", "meds_taken", "numbness", "fall"],
            "additionalProperties": False,
        },
        "medication_mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "taken": {"type": "boolean"}},
                "required": ["name", "taken"],
            },
        },
        "about_other_person": {"type": "boolean"},
        "asks_identity": {"type": "boolean"},
    },
    "required": ["route", "operational_kind", "topic_kind", "topic", "is_actual_report", "symptoms", "temperature_f", "is_consent",
                 "checkin_answers", "medication_mentions", "about_other_person", "asks_identity"],
}

PROMPT = """You are the message classifier for Foggy, an AI recovery helper app used by one patient after surgery.
You never write replies. Read the patient's newest message, with the recent conversation, the app state and
the patient's care plan, and return JSON describing it. The app's code uses your JSON to decide what to do.

ROUTES (pick one; when several apply, the earliest in this list wins; OPERATIONAL is separate):
1. EMERGENCY_911: the patient reports chest pain, trouble breathing or shortness of breath, heavy bleeding,
   fainting or passing out, thoughts of self-harm, or asks you to call 911. Counts even if the patient also says
   they feel fine, the pain score is low, it already stopped, or they change the subject. An actual emergency
   happening now to someone with the patient also counts.
2. CALL_SURGEON: the patient reports a fever (any stated temperature; code checks the number), redness that is
   spreading or increasing, more or new drainage from the incision, calf pain or swelling, pain they call
   uncontrolled / out of control / not helped by medicine, a fall, or new numbness, tingling, or skin color
   change. Also when such a report comes with a medication request.
3. REFUSE_DOSE_CHANGE: asks to change a medicine: take more, less, double, extra, half, skip, stop, switch,
   reschedule, or a different amount than the plan says.
4. START_CHECKIN: asks for a check-in, or says they feel off, unwell, or not right without naming a specific
   warning sign.
5. NOT_IN_PLAN: anything the care plan below does not explicitly answer. This includes missed doses, medicines or
   supplements that are not in the plan, alcohol or cannabis, timing or limits the plan does not give (such as
   hours between oxycodone doses), going back to work, travel, second opinions about the surgery, diagnosis
   questions, questions about another person's care (a family member or friend), feelings like fear or sadness,
   and anything unrelated to recovery (jokes, sports, weather).
6. ANSWER_FROM_PLAN: a question the care plan explicitly answers, including reading back a medicine instruction
   exactly as written, and "what should I do if ..." questions the plan answers.
OPERATIONAL: social turns and replies about the conversation itself: acknowledgments ("will do", "okay", "got
   it", "sounds good"), thanks, greetings ("hi", "hello?", "hey Foggy"), goodbyes ("bye", "talk later", "that's
   all"), brief well-being updates that name no symptom ("I'm doing fine", "feeling better today", "had a good
   night"), yes/no/unclear replies to Foggy's last question, check-in answers, questions about who or what Foggy
   is (doctor? nurse? human? AI?), and questions about what Foggy can do (call, text, message the care team).
   Social turns are never NOT_IN_PLAN. A well-being update that also mentions a symptom or warning sign is not
   social: route it by the symptom ("I'm fine but I can't breathe" is EMERGENCY_911).

FIELDS
- is_actual_report: true if the message reports something actually happening now or recently to the patient (or
  an emergency happening now to someone with them). false for denials ("no chest pain"), hypotheticals and
  questions ("what if I get chest pain?", "when should I call 911?"), quotes or examples ("the plan says call
  911 for chest pain"), and old unrelated history ("I had pneumonia years ago").
- symptoms: the warning signs the message actually reports. Empty for denials and hypotheticals.
- temperature_f: the temperature the patient reports, in Fahrenheit (convert Celsius), else -1.
- is_consent: only when STATE shows a pending offer to message the care team: "yes", "no", or "unclear" for a
  reply to that offer ("maybe", "I don't know"). A new question or new information is "n/a". "n/a" when there is
  no pending offer.
- checkin_answers: what the message says about the four check-in questions, including volunteered answers:
  pain 0-10 (-1 if not given); meds_taken yes / no / unclear ("I think so", "most of them") / not_given;
  numbness yes / no / not_given (new numbness, tingling, or color change); fall yes / no / not_given. When STATE
  says a check-in question is waiting, a bare "yes", "no", or number answers that question. meds_taken is "yes"
  when the patient says they took all of their medicines ("I took everything this morning").
- medication_mentions: each medicine the patient says they took or did not take, as {name, taken}, using the
  medicine's name ("I skipped the aspirin" -> [{name: "aspirin", taken: false}]; "took my Tylenol and forgot the
  aspirin" -> acetaminophen taken true, aspirin taken false). Missed, forgot, skipped = taken false. Empty when no
  medicine is named, and for questions ("can I take my aspirin later?").
- about_other_person: the question is about someone other than the patient.
- asks_identity: asks who or what Foggy is, or whether it is a doctor, nurse, human, or AI.
- operational_kind: for OPERATIONAL only: acknowledgment, thanks, greeting, goodbye, wellbeing (a brief update
  with no symptom), identity, or capability. "none" for consent and check-in answers and for every other route.
- topic_kind: the closest label for the message.
- topic: for NOT_IN_PLAN only, 2 to 6 plain words that complete "Your care plan doesn't cover ___", for example
  "going back to work", "taking ibuprofen", "drinking alcohol". Otherwise "".

EXAMPLES (for illustration; the patient's own plan is below)
"Can I take a bath?" -> ANSWER_FROM_PLAN, plan_question (the plan covers soaking)
"My chest feels tight but I'm fine otherwise. When is PT?" -> EMERGENCY_911, symptoms [chest_pain], is_actual_report true
"No chest pain, just wondering about my dressing" -> ANSWER_FROM_PLAN, symptoms [], is_actual_report false
"What should I do if I can't breathe?" -> ANSWER_FROM_PLAN, symptoms [], is_actual_report false
"I passed out in the kitchen an hour ago" -> EMERGENCY_911, symptoms [fainting]
"Fever is 101.2" -> CALL_SURGEON, symptoms [fever], temperature_f 101.2 (code compares the number)
"My incision is leaking more today" -> CALL_SURGEON, symptoms [redness_or_drainage]
"I slipped in the bathroom" -> CALL_SURGEON, symptoms [fall]
"The pain is way out of control, can I take two oxycodone?" -> CALL_SURGEON, symptoms [uncontrolled_pain]
"Can I take my aspirin once a day instead?" -> REFUSE_DOSE_CHANGE, dose_change
"Should I keep taking oxycodone?" -> REFUSE_DOSE_CHANGE, dose_change
"I forgot my acetaminophen last night" -> NOT_IN_PLAN, missed_dose, topic "a missed dose"
"Is Tylenol PM okay?" -> NOT_IN_PLAN, unlisted_medication, topic "Tylenol PM"
"Is a beer okay with dinner?" -> NOT_IN_PLAN, alcohol_or_cannabis, topic "drinking alcohol"
"What is the most oxycodone I can take in a day?" -> NOT_IN_PLAN, dose_interval_or_max
"My husband's stitches look red, what should he do?" -> NOT_IN_PLAN, family_member, about_other_person true
"Can I go back to the gym?" -> NOT_IN_PLAN, other, topic "going back to the gym"
"I'm so worried about all this" -> NOT_IN_PLAN, feelings
"What's the capital of France?" -> NOT_IN_PLAN, non_medical
"Are you a real nurse?" -> OPERATIONAL, operational_kind identity, asks_identity true
"Can you call my surgeon for me?" -> OPERATIONAL, operational_kind capability
"Will do" -> OPERATIONAL, operational_kind acknowledgment
"Thanks so much Foggy!" -> OPERATIONAL, operational_kind thanks
"Hello? Is this Foggy?" -> OPERATIONAL, operational_kind greeting
"Okay that's all for today, bye" -> OPERATIONAL, operational_kind goodbye
"Honestly I'm feeling a lot better than yesterday" -> OPERATIONAL, operational_kind wellbeing
"I'm fine but my calf is swollen" -> CALL_SURGEON, symptoms [calf_pain_or_swelling]
"I feel kind of weird today" -> START_CHECKIN, checkin_request
"Let's do the check-in, pain is about a 3" -> START_CHECKIN, checkin_answers.pain 3
(STATE: check-in waiting for meds_taken) "yep" -> OPERATIONAL, checkin_answer, meds_taken yes, is_consent n/a
(STATE: check-in asking about the 8 AM aspirin dose) "no I forgot that one" -> OPERATIONAL, checkin_answer,
   meds_taken no, medication_mentions []
"Let's check in, I took everything this morning" -> START_CHECKIN, checkin_answers.meds_taken yes
(STATE: pending offer to message care team) "yes please" -> OPERATIONAL, consent_answer, is_consent yes
(STATE: pending offer to message care team) "okay, got it" -> OPERATIONAL, acknowledgment, is_consent unclear
(STATE: pending offer to message care team) "can I shower though?" -> ANSWER_FROM_PLAN, is_consent n/a
"""


@dataclass
class Classification:
    route: str
    topic_kind: str = "other"
    topic: str = ""
    is_actual_report: bool = False
    symptoms: list[str] = field(default_factory=list)  # router sign names
    temperature_f: float | None = None
    is_consent: str = "n/a"
    checkin_answers: dict = field(default_factory=dict)  # only the answers given
    medication_mentions: list[dict] = field(default_factory=list)  # [{name, taken}]
    about_other_person: bool = False
    asks_identity: bool = False
    operational_kind: str = "none"


def _state_text(state: dict) -> str:
    parts = []
    pending = state.get("pending_action")
    if pending:
        parts.append(f"Pending offer: Foggy asked whether to send a message to the care team about: "
                     f"\"{pending.get('patient_words', '')[:200]}\". Waiting for yes or no.")
    checkin = state.get("checkin_state")
    if checkin and checkin.get("awaiting"):
        waiting = checkin["awaiting"]
        meds = checkin.get("meds") or {}
        if waiting == "meds_taken" and meds.get("queue"):
            dose = meds["queue"][0]
            waiting = (f"meds_taken (Foggy asked whether the patient took the {dose.get('name')} "
                       f"{dose.get('dosage', '')} dose due at {dose.get('hour', 0):02d}:{dose.get('minute', 0):02d} today)")
        elif waiting == "meds_taken" and meds.get("prn"):
            waiting = f"meds_taken (Foggy asked whether the patient needed any {meds['prn'][0].get('name')} today)"
        parts.append(f"Check-in in progress, waiting for: {waiting}. "
                     f"Answers so far: {json.dumps(checkin.get('answers', {}))}.")
    return " ".join(parts) or "No pending offer. No check-in in progress."


def build_messages(message: str, chunks: list[dict], history: list[dict], state: dict) -> list[dict]:
    plan = "\n".join(f"- {c.get('section') or 'Care plan'}: {c['content']}" for c in chunks) or "(no care plan loaded)"
    convo = "\n".join(
        f"{'Patient' if h['role'] == 'patient' else 'Foggy'}: {h['content']}" for h in history[-6:]
    ) or "(none)"
    user = (f"CARE PLAN:\n{plan}\n\nSTATE: {_state_text(state)}\n\nRECENT CONVERSATION:\n{convo}\n\n"
            f"NEWEST PATIENT MESSAGE:\n{message}")
    return [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}]


def parse(data: dict) -> Classification:
    route = data.get("route")
    if route not in ROUTES:
        raise ai_service.ProviderError("classifier returned an unknown route")
    answers_in = data.get("checkin_answers") or {}
    answers: dict = {}
    pain = answers_in.get("pain")
    if isinstance(pain, (int, float)) and 0 <= pain <= 10 and float(pain).is_integer():
        answers["pain"] = int(pain)
    if answers_in.get("meds_taken") in ("yes", "no", "unclear"):
        answers["meds_taken"] = answers_in["meds_taken"]
    for key in ("numbness", "fall"):
        if answers_in.get(key) in ("yes", "no"):
            answers[key] = answers_in[key]
    temp = data.get("temperature_f")
    temp = float(temp) if isinstance(temp, (int, float)) and 90 <= temp <= 110 else None
    mentions = [
        {"name": str(m["name"]).strip()[:60], "taken": m["taken"]}
        for m in (data.get("medication_mentions") or [])
        if isinstance(m, dict) and isinstance(m.get("taken"), bool) and str(m.get("name") or "").strip()
    ]
    return Classification(
        route=route,
        topic_kind=data.get("topic_kind") if data.get("topic_kind") in TOPIC_KINDS else "other",
        topic=str(data.get("topic") or "").strip(),
        is_actual_report=bool(data.get("is_actual_report")),
        symptoms=[SYMPTOM_TO_SIGN[s] for s in (data.get("symptoms") or []) if s in SYMPTOM_TO_SIGN],
        temperature_f=temp,
        is_consent=data.get("is_consent") if data.get("is_consent") in ("yes", "no", "unclear") else "n/a",
        checkin_answers=answers,
        medication_mentions=mentions,
        about_other_person=bool(data.get("about_other_person")),
        asks_identity=bool(data.get("asks_identity")),
        operational_kind=(data.get("operational_kind") if route == "OPERATIONAL"
                          and data.get("operational_kind") in OPERATIONAL_KINDS else "none"),
    )


def classify_message(message: str, chunks: list[dict], history: list[dict], state: dict) -> Classification | None:
    """The model's reading of the message, or None when no provider is available (rules only)."""
    if ai_service.select_provider() == "none":
        return None
    try:
        data = ai_service.llm_json(build_messages(message, chunks, history, state), SCHEMA, "foggy_route")
        return parse(data)
    except ai_service.ProviderError as e:
        log.warning("foggy.classify unavailable (%s); using rules only.", e)
        return None
