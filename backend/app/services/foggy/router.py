"""One Foggy turn: pre-checks, priority order, conversation state, actions, reply.

The model classifies (classify.py) and phrases plan answers (phrase.py); this module decides
and acts. Priority (docs/foggy-policy.md): EMERGENCY_911 > aside ("hold on") > pending consent >
CALL_SURGEON > REFUSE_DOSE_CHANGE > check-in > identity/capability > social turns (acknowledgment,
thanks, greeting, goodbye, well-being) > NOT_IN_PLAN > ANSWER_FROM_PLAN.
Emergencies are checked before anything else, including a pending offer or a check-in. Social turns
never change the state: with an offer pending they count as an unclear answer (asked again once),
and a goodbye counts as "no".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, Patient, SymptomLog
from app.services.foggy import actions as actions_mod
from app.services.foggy import classify as classify_mod
from app.services.foggy import lexicon, phrase
from app.services.foggy import state as state_mod
from app.services.foggy.classify import Classification

log = logging.getLogger("cloudcare.foggy")

HISTORY_TURNS = 6
CHECKIN_STEPS = ("pain", "meds_taken", "numbness", "fall")
CALL_KINDS = ("redness_drainage", "calf_pain_swelling", "uncontrolled_pain", "fall", "numbness_tingling_color")
# Out-of-scope rules that win over a model's "the plan covers it": the plan never has these.
FORCED_NOT_IN_PLAN = ("missed_dose", "dose_interval_or_max", "unlisted_medication", "alcohol_or_cannabis")


@dataclass
class TurnResult:
    route: str
    content: str
    citations: list = field(default_factory=list)
    answered_from_plan: bool | None = None
    red_flag: bool = False
    offer_contact: bool = False
    pending_action: dict | None = None   # public shape {kind, recipient, reason}
    action_result: dict | None = None
    checkin: dict | None = None          # public shape {step, answers}
    escalated: bool = False
    message: ChatMessage | None = None   # the saved assistant message
    model_used: bool = False             # every model call this turn succeeded (False = rules only, or degraded)


@dataclass
class _Ctx:
    message: str
    name: str
    chunks: list[dict]
    history: list[dict]
    plan_text: str
    first_checkin: bool
    source: str
    acts: actions_mod.TurnActions
    patient_msg_id: str
    cls: Classification | None = None
    pending: dict | None = None
    checkin: dict | None = None
    # outputs
    route: str = "OPERATIONAL"
    text: str = ""
    citations: list = field(default_factory=list)
    answered_from_plan: bool | None = None
    new_pending: dict | None = None
    action_result: dict | None = None
    checkin_done: dict | None = None
    model_degraded: bool = False  # a model call was needed but failed (rules answered instead)


# ---- entry point ----------------------------------------------------------------------

def answer_turn(db: Session, patient: Patient, message: str, source: str = "chat") -> TurnResult:
    """Handles one patient message end to end. Adds rows to the session; the caller commits."""
    from app.routes.patients import active_care_plan  # route helper; imported here to avoid a cycle

    recent = db.scalars(
        select(ChatMessage).where(ChatMessage.patient_id == patient.id)
        .order_by(ChatMessage.created_at.desc()).limit(HISTORY_TURNS)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
    plan = active_care_plan(db, patient.id)
    chunks = [{"id": c.id, "section": c.section, "content": c.content} for c in (plan.chunks if plan else [])]
    st = state_mod.load(db, patient.id)
    first_checkin = db.scalar(
        select(SymptomLog.id).where(SymptomLog.patient_id == patient.id).limit(1)
    ) is None

    # Explicit timestamps: Postgres now() is the transaction start, which would give the
    # question and the reply the same created_at and an unstable order in the history.
    patient_msg = ChatMessage(patient_id=patient.id, role="patient", content=message,
                              created_at=datetime.now(timezone.utc))
    db.add(patient_msg)
    db.flush()

    full_name = (patient.user.full_name if patient.user else "") or ""
    ctx = _Ctx(
        message=message, name=full_name.split()[0] if full_name.strip() else "there", chunks=chunks,
        history=history, plan_text=" ".join(c["content"] for c in chunks), first_checkin=first_checkin,
        source=source, acts=actions_mod.TurnActions(db, patient, patient_msg.id),
        patient_msg_id=str(patient_msg.id), pending=st["pending_action"], checkin=st["checkin_state"],
    )
    if _needs_classifier(ctx):
        ctx.cls = classify_mod.classify_message(message, chunks, history, st)
    _decide(ctx)

    caps = actions_mod.capabilities()
    if ctx.new_pending and not caps["message_care_team"]:
        ctx.new_pending = None
        ctx.text = phrase.split_sentences(ctx.text)[0] + " Please contact your medical team directly."
    content = phrase.enforce(ctx.text, ctx.route, emergency_call_assist=caps["emergency_call_assist"])

    reply = ChatMessage(
        patient_id=patient.id, role="assistant", content=content, citations=ctx.citations,
        answered_from_plan=ctx.answered_from_plan, red_flag=ctx.route == "EMERGENCY_911", route=ctx.route,
        created_at=max(datetime.now(timezone.utc), patient_msg.created_at + timedelta(milliseconds=1)),
    )
    db.add(reply)
    state_mod.save(db, patient.id, ctx.new_pending, ctx.checkin)
    db.flush()
    log.info("foggy.turn route=%s offer=%s action=%s checkin=%s model=%s", ctx.route, bool(ctx.new_pending),
             (ctx.action_result or {}).get("status"), _public_checkin(ctx) is not None, ctx.cls is not None)

    return TurnResult(
        route=ctx.route, content=content, citations=ctx.citations, answered_from_plan=ctx.answered_from_plan,
        red_flag=ctx.route == "EMERGENCY_911", offer_contact=ctx.new_pending is not None,
        pending_action=_public_pending(ctx.new_pending), action_result=ctx.action_result,
        checkin=_public_checkin(ctx), escalated=ctx.acts.escalated, message=reply,
        model_used=ctx.cls is not None and not ctx.model_degraded,
    )


def _needs_classifier(ctx: _Ctx) -> bool:
    """Skip the model for replies the rules already understand (faster, same result)."""
    t = ctx.message
    reported_emergency = any(h.reported for h in lexicon.emergency_hits(t))
    if reported_emergency:
        return True  # the model may still recognize a quotation or example
    if lexicon.is_aside(t) or lexicon.social_kind(t):
        return False  # whole-message social phrases; they can carry no symptom
    if ctx.pending and lexicon.yes_no(t):
        return False
    if ctx.checkin and ctx.checkin.get("awaiting") and _bare_answer(ctx) is not None:
        return False
    return True


# ---- decision ---------------------------------------------------------------------------

def _decide(ctx: _Ctx) -> None:
    if _is_emergency(ctx):
        ctx.acts.emergency_alert(ctx.message)
        ctx.route, ctx.text = "EMERGENCY_911", phrase.EMERGENCY_FIRST
        ctx.new_pending, ctx.checkin = None, None  # 911 replaces any routine offer or check-in
        return

    if lexicon.is_aside(ctx.message):
        # "Hold on": nothing was answered, so an offer or check-in waits exactly as it was.
        ctx.route, ctx.text = "OPERATIONAL", phrase.ASIDE
        ctx.new_pending = ctx.pending
        return

    if ctx.pending and _handle_consent(ctx):
        return

    triggers = _call_triggers(ctx)

    if ctx.checkin and _handle_checkin_answer(ctx, triggers):
        return

    if triggers:
        _call_surgeon(ctx, triggers)
        return

    cls = ctx.cls
    t = ctx.message
    other_person = bool(cls and cls.about_other_person)

    if not other_person and (lexicon.dose_change_requested(t) or (cls and cls.route == "REFUSE_DOSE_CHANGE")):
        ctx.route = "REFUSE_DOSE_CHANGE"
        ctx.text = phrase.refuse_dose_change(lexicon.is_stop_request(t))
        ctx.answered_from_plan = False
        _offer(ctx, "Medication change request")
        return

    if lexicon.checkin_requested(t) or (cls and cls.route == "START_CHECKIN"):
        _start_checkin(ctx)
        return

    if lexicon.asks_identity(t) or (cls and (cls.asks_identity or cls.operational_kind == "identity")):
        ctx.route, ctx.text = "OPERATIONAL", phrase.IDENTITY
        return

    if lexicon.asks_capability(t) or (cls and (cls.topic_kind == "capability" or cls.operational_kind == "capability")):
        ctx.route, ctx.text = "OPERATIONAL", phrase.CAPABILITY
        _offer(ctx, "Patient asked to contact the care team")
        return

    talk = _social(ctx)
    if talk:
        ctx.route = "OPERATIONAL"
        if ctx.checkin and ctx.checkin.get("awaiting"):
            ctx.text = "Let's finish your check-in. " + _checkin_prompt(ctx)
        else:
            recent = [h["content"] for h in ctx.history if h["role"] == "assistant"]
            ctx.text = phrase.operational(talk, ctx.name, recent, t)
        return

    kind, matched = lexicon.out_of_scope_kind(t)
    if kind == "alcohol_or_cannabis" and "alcohol" in ctx.plan_text.lower() and cls is not None:
        kind = None  # the plan mentions alcohol: let the plan answer the covered part
    if other_person:
        kind = "family_member"
    if kind in FORCED_NOT_IN_PLAN or kind == "family_member" or (cls is None and kind):
        _not_in_plan(ctx, kind, matched)
        return
    if cls and cls.route == "NOT_IN_PLAN":
        _not_in_plan(ctx, _model_kind(cls, kind), matched)
        return
    if cls and cls.route == "OPERATIONAL" and cls.topic_kind not in ("plan_question", "other_medical", "other"):
        ctx.route, ctx.text = "OPERATIONAL", phrase.operational("other", ctx.name)
        return

    _answer_from_plan(ctx, kind, matched)


def _social_only(ctx: _Ctx) -> str | None:
    """Like _social, but without treating a bare yes/no as social (used while an offer is pending)."""
    kind = lexicon.social_kind(ctx.message)
    cls = ctx.cls
    if kind is None and cls is not None and cls.route == "OPERATIONAL" and cls.operational_kind in \
            lexicon.SOCIAL_KINDS and not cls.symptoms and not lexicon.mentions_symptom(ctx.message):
        kind = cls.operational_kind
    return kind


def _social(ctx: _Ctx) -> str | None:
    """The social kind of the message (acknowledgment, thanks, greeting, goodbye, wellbeing), or None.
    The word lists decide first; the model's label counts only when the message names no symptom."""
    kind = _social_only(ctx)
    if kind:
        return kind
    cls = ctx.cls
    if (cls is not None and cls.route == "OPERATIONAL" and cls.topic_kind in ("greeting", "thanks")
            and not cls.symptoms and not lexicon.mentions_symptom(ctx.message)):
        return cls.topic_kind
    if lexicon.yes_no(ctx.message):
        return "acknowledgment"  # a bare yes / no / maybe with nothing waiting for it
    return None


def _is_emergency(ctx: _Ctx) -> bool:
    hits = lexicon.emergency_hits(ctx.message)
    reported = any(h.reported for h in hits)
    cls = ctx.cls
    if cls is None:
        return reported
    model_sign = cls.is_actual_report and any(s in lexicon.EMERGENCY_SIGNS for s in cls.symptoms)
    model_route = cls.route == "EMERGENCY_911" and (cls.is_actual_report or reported)
    # A word-list hit counts unless the model says the message is not an actual report
    # (a quotation, example, or other non-report the clause check missed).
    return model_sign or model_route or (reported and cls.is_actual_report) or (
        reported and cls.route == "EMERGENCY_911")


def _call_triggers(ctx: _Ctx) -> list[str]:
    """Plan call triggers and product call rules that the patient actually reports."""
    cls = ctx.cls
    if cls is not None and (cls.about_other_person or not cls.is_actual_report):
        lexical = []
        fever, temp = False, None
    else:
        lexical = [h.kind for h in lexicon.call_trigger_hits(ctx.message) if h.reported]
        fever, temp = lexicon.fever_reported(ctx.message)
    kinds = set(lexical)
    if cls is not None and cls.is_actual_report and not cls.about_other_person:
        kinds |= {s for s in cls.symptoms if s in CALL_KINDS}
        if temp is None and cls.temperature_f is not None and "fever" in cls.symptoms:
            fever, temp = True, cls.temperature_f
    if fever and temp is not None and temp > lexicon.FEVER_LIMIT_F:  # strictly over 101.5 F
        kinds.add("fever")
    return [k for k in phrase.TRIGGER_ORDER if k in kinds]


def _model_kind(cls: Classification, lexical_kind: str | None) -> str:
    if cls.topic_kind in ("missed_dose", "unlisted_medication", "dose_interval_or_max", "alcohol_or_cannabis",
                          "second_opinion", "work_or_travel", "family_member", "non_medical", "feelings",
                          "other_medical"):
        return cls.topic_kind
    return lexical_kind or "other"


# ---- routes -----------------------------------------------------------------------------

def _offer(ctx: _Ctx, reason: str) -> None:
    ctx.new_pending = {
        "kind": "message_care_team", "recipient": "care_team", "reason": reason, "origin_route": ctx.route,
        "patient_words": ctx.message.strip(), "chat_message_id": ctx.patient_msg_id, "asked_again": False,
    }


def _call_surgeon(ctx: _Ctx, triggers: list[str]) -> None:
    ctx.route = "CALL_SURGEON"
    ctx.text, reason = phrase.call_surgeon(triggers, ctx.plan_text)
    _offer(ctx, reason)


def _not_in_plan(ctx: _Ctx, kind: str | None, matched: str) -> None:
    kind = kind or "other"
    topic = ctx.cls.topic if ctx.cls and ctx.cls.topic else ""
    if not topic and kind in ("unlisted_medication", "alcohol_or_cannabis") and matched:
        topic = matched if kind == "unlisted_medication" else ""
    relation = lexicon.family_relation(ctx.message)
    ctx.route = "NOT_IN_PLAN"
    ctx.text, reason = phrase.not_in_plan(kind, topic, ctx.name, relation)
    ctx.answered_from_plan = False
    _offer(ctx, reason)


def _answer_from_plan(ctx: _Ctx, kind: str | None, matched: str) -> None:
    ans = phrase.plan_answer(ctx.message, ctx.chunks, ctx.history) if ctx.cls is not None else None
    if ans is None:
        ctx.model_degraded = ctx.cls is not None
        ans = phrase.fallback_plan_answer(ctx.message, ctx.chunks)
    if ans and ans.get("answered_from_plan"):
        ctx.route = "ANSWER_FROM_PLAN"
        ctx.text = ans["content"]
        ctx.citations = ans.get("citations") or []
        ctx.answered_from_plan = True
        return
    _not_in_plan(ctx, kind, matched)


# ---- consent ------------------------------------------------------------------------------

def _handle_consent(ctx: _Ctx) -> bool:
    """Answers the pending offer. False when the message is something else (offer dropped)."""
    pending = ctx.pending
    answer = lexicon.yes_no(ctx.message)
    social = _social_only(ctx)
    if social == "goodbye" and answer != "yes":
        answer = "no"  # the patient is leaving: nothing is sent
    elif social and answer != "no" and not lexicon.explicit_yes(ctx.message):
        answer = "unclear"  # "okay", "got it", "thanks" acknowledge; they don't agree to send anything
    if answer is None and ctx.cls is not None and ctx.cls.is_consent != "n/a":
        answer = ctx.cls.is_consent
    if answer is None and ctx.cls is None and len(ctx.message.split()) <= 3 and "?" not in ctx.message:
        answer = "unclear"
    if answer is None:
        return False  # a new request: the old offer is not carried forward

    ctx.route = "OPERATIONAL"
    resume = ""
    if ctx.checkin and ctx.checkin.get("awaiting"):
        resume = " " + _checkin_prompt(ctx)

    if answer == "yes":
        result = ctx.acts.message_care_team(pending, "yes")
        ctx.action_result = result
        if result["status"] == "sent":
            if pending.get("origin_route") == "CALL_SURGEON" and not resume:
                ctx.text = phrase.SENT + " Please still call your surgeon or medical team."
            else:
                ctx.text = phrase.SENT + resume
        else:
            ctx.text = phrase.SEND_FAILED
        return True
    if answer == "no":
        if social == "goodbye" and not resume:
            ctx.text = phrase.NOT_SENT + (f" Take care, {ctx.name}." if ctx.name != "there" else " Take care.")
        else:
            ctx.text = phrase.NOT_SENT + (resume or " Let me know if you change your mind.")
        return True
    # unclear: ask once more, then let it go
    if not pending.get("asked_again"):
        ctx.new_pending = {**pending, "asked_again": True}
        ctx.text = "Just to check, would you like me to send a message to your care team? Please answer yes or no."
    else:
        ctx.text = "Okay, I won't send anything for now. You can ask me anytime."
    return True


# ---- check-in ------------------------------------------------------------------------------

_PARSERS = {
    "pain": lexicon.parse_pain,
    "meds_taken": lexicon.parse_meds,
    "numbness": lexicon.parse_numbness,
    "fall": lexicon.parse_fall,
}


def _bare_answer(ctx: _Ctx):
    """The rules' reading of the message as an answer to the waiting question (None if it isn't one)."""
    checkin = ctx.checkin or {}
    if checkin.get("clarifying"):
        return ctx.message if _looks_like_answer(ctx.message, allow_words=12) else None
    awaiting = checkin.get("awaiting")
    if not awaiting:
        return None
    return _PARSERS[awaiting](ctx.message, True)


def _looks_like_answer(message: str, allow_words: int = 6) -> bool:
    return "?" not in message and len(message.split()) <= allow_words


def _extract_answers(ctx: _Ctx, awaiting: str | None) -> dict:
    out: dict = {}
    model = ctx.cls.checkin_answers if ctx.cls else {}
    for step in CHECKIN_STEPS:
        bare = step == awaiting
        value = _PARSERS[step](ctx.message, bare)
        if value is None and step in model:
            value = model[step]
        if value is not None:
            out[step] = value
    return out


def _next_step(answers: dict) -> str | None:
    return next((s for s in CHECKIN_STEPS if s not in answers), None)


def _checkin_prompt(ctx: _Ctx) -> str:
    checkin = ctx.checkin or {}
    if checkin.get("clarifying"):
        return phrase.CHECKIN_CLARIFY[checkin["clarifying"]]
    return phrase.checkin_question(checkin["awaiting"], checkin.get("first", False))


def _start_checkin(ctx: _Ctx) -> None:
    ctx.route = "START_CHECKIN"
    if ctx.checkin and ctx.checkin.get("awaiting"):
        ctx.text = "Let's keep going with your check-in. " + _checkin_prompt(ctx)
        return
    ctx.checkin = {"awaiting": None, "answers": {}, "clarifying": None, "first": ctx.first_checkin,
                   "started_at": datetime.now(timezone.utc).isoformat()}
    answers = _extract_answers(ctx, None)
    _advance(ctx, answers, intro=f"Let's do a short check-in, {ctx.name}.", triggers=[])


def _handle_checkin_answer(ctx: _Ctx, triggers: list[str]) -> bool:
    checkin = ctx.checkin
    if lexicon.CHECKIN_CANCEL.match(lexicon.normalize(ctx.message)):
        ctx.checkin = None
        ctx.route, ctx.text = "OPERATIONAL", "Okay, we can finish your check-in later."
        return True
    awaiting = checkin.get("awaiting")
    answers = dict(checkin.get("answers") or {})

    if checkin.get("clarifying") == "meds_taken":
        if _bare_answer(ctx) is None and not lexicon.MED_WORDS.search(lexicon.normalize(ctx.message)):
            return False  # something else; route it normally and keep the check-in
        answers["meds_detail"] = ctx.message.strip()[:200]
        ctx.checkin = {**checkin, "clarifying": None}
        _advance(ctx, answers, intro="", triggers=triggers)
        return True

    updates = _extract_answers(ctx, awaiting)
    if awaiting not in updates and not (set(updates) & set(CHECKIN_STEPS)):
        if awaiting == "pain" and "uncontrolled_pain" in triggers:
            return False  # "it's out of control": CALL_SURGEON handles it, check-in kept
        if _looks_like_answer(ctx.message) and not triggers and not lexicon.dose_change_requested(ctx.message):
            ctx.route, ctx.text = "START_CHECKIN", phrase.CHECKIN_REASK[awaiting]
            return True
        return False
    for step, value in updates.items():
        if step == awaiting or step not in answers:  # never overwrite an earlier answer with a guess
            answers[step] = value
    _advance(ctx, answers, intro="", triggers=triggers)
    return True


def _advance(ctx: _Ctx, answers: dict, intro: str, triggers: list[str]) -> None:
    """Stores answers, asks the next missing question, or saves the finished check-in."""
    triggers = list(triggers)
    if answers.get("numbness") == "yes" and "numbness_tingling_color" not in triggers:
        triggers.append("numbness_tingling_color")
    if answers.get("fall") == "yes" and "fall" not in triggers:
        triggers.append("fall")
    triggers = [k for k in phrase.TRIGGER_ORDER if k in triggers]

    checkin = {**(ctx.checkin or {}), "answers": answers}
    clarify = None
    if answers.get("meds_taken") in ("no", "unclear") and "meds_detail" not in answers and not checkin.get(
            "asked_meds_detail"):
        clarify = "meds_taken"
        checkin["asked_meds_detail"] = True
    nxt = _next_step(answers)
    checkin["awaiting"] = nxt
    checkin["clarifying"] = clarify
    ctx.checkin = checkin

    if nxt is None and clarify is None:
        result = ctx.acts.save_checkin(answers, ctx.source)
        ctx.checkin_done = {"step": "done", "answers": _public_answers(answers)}
        ctx.checkin = None
        if triggers:
            _call_surgeon(ctx, triggers)
            return
        ctx.route = "OPERATIONAL"
        if result["escalated"]:
            ctx.text = f"Thanks for checking in, {ctx.name}. Your answers are in your care team's queue for review."
        else:
            ctx.text = f"Thanks for checking in, {ctx.name}. I saved your answers."
        return

    if triggers:
        _call_surgeon(ctx, triggers)  # interrupt; the check-in continues after the offer is answered
        return
    ctx.route = "START_CHECKIN"
    question = _checkin_prompt(ctx)
    ctx.text = f"{intro} {question}".strip()


# ---- public shapes ---------------------------------------------------------------------------

def _public_pending(pending: dict | None) -> dict | None:
    if not pending:
        return None
    return {"kind": pending["kind"], "recipient": pending["recipient"], "reason": pending["reason"]}


def _public_answers(answers: dict) -> dict:
    return {k: v for k, v in answers.items() if k in CHECKIN_STEPS or k == "meds_detail"}


def _public_checkin(ctx: _Ctx) -> dict | None:
    if ctx.checkin_done:
        return ctx.checkin_done
    if not ctx.checkin or not ctx.checkin.get("awaiting") and not ctx.checkin.get("clarifying"):
        return None
    awaiting = ctx.checkin.get("awaiting") or "meds_taken"
    step = CHECKIN_STEPS.index(awaiting) + 1
    if ctx.checkin.get("clarifying"):
        step = CHECKIN_STEPS.index(ctx.checkin["clarifying"]) + 1
    return {"step": step, "answers": _public_answers(ctx.checkin.get("answers") or {})}
