"""Reply wording for each route, and the rules every reply passes before it is shown.

Plan answers come from the model (grounded and fact-checked in ai_service.plan_answer),
or from the plan's own sentences when no model is available. Every other route uses fixed
wording filled with what the classifier extracted (such as the topic), so safety-critical
sentences never depend on generated text. enforce() then applies the hard rules: at most
two sentences, "911" written as digits, and the forced emergency wording.
"""

from __future__ import annotations

import re

from app.services import ai_service

EMERGENCY_FIRST = "Call 911 now."
NO_EMERGENCY_CALLS = "I can't place emergency calls."
OFFER = "Would you like me to send a message to your care team?"
OFFER_TOO = "Would you like me to send a message to your care team too?"
IDENTITY = "I'm an AI recovery helper, not a doctor or nurse. I can help explain your surgeon's care plan."
SENT = "I've sent your message to your care team's queue."
SEND_FAILED = "I couldn't send the message. Please call your medical team."
NOT_SENT = "Okay, I won't send anything."

MAX_SENTENCES = 2

# ---- enforcement ----------------------------------------------------------------------

_ABBREV = re.compile(r"\b(Dr|Mr|Mrs|Ms|St|vs|approx|e\.g|i\.e)\.$", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    """Sentences, keeping decimals like 101.5 and titles like Dr. together."""
    parts = re.split(r"(?<=[.!?])\s+(?=[\"'(]?[A-Z0-9])", (text or "").strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out and _ABBREV.search(out[-1]):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


def spell_911(text: str) -> str:
    text = re.sub(r"\bnine[\s-]+one[\s-]+one\b", "911", text, flags=re.IGNORECASE)
    return re.sub(r"\b9[\s.-]1[\s.-]1\b", "911", text)


def clean_style(text: str) -> str:
    """No Markdown, bullets, or stray symbols in a reply that may be spoken."""
    text = re.sub(r"[*_#`>]+", "", text or "")
    text = re.sub(r"^\s*(?:[-•]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def cap_sentences(text: str, limit: int = MAX_SENTENCES) -> str:
    return " ".join(split_sentences(text)[:limit])


def enforce(text: str, route: str, emergency_call_assist: bool = False) -> str:
    """Hard rules for every reply. EMERGENCY_911 wording is fixed by code, never generated."""
    if route == "EMERGENCY_911":
        second = "Would you like me to help start the call?" if emergency_call_assist else NO_EMERGENCY_CALLS
        return f"{EMERGENCY_FIRST} {second}"
    text = cap_sentences(spell_911(clean_style(text)))
    return text or "I'm here to help with your care plan."


# ---- route wording ----------------------------------------------------------------------

_TOPIC_OK = re.compile(r"^[a-z][a-z0-9 ,'/-]{1,60}$", re.IGNORECASE)
_TOPIC_BAD = re.compile(r"\b(safe|okay|fine|should|recommend|notif|sent|allowed|cleared|dose of|\d)\b", re.IGNORECASE)


def clean_topic(topic: str) -> str | None:
    """Classifier topic, only if it is a short plain noun phrase."""
    t = (topic or "").strip().strip(".?!").strip()
    t = re.sub(r"^(?:about|whether|if)\s+", "", t, flags=re.IGNORECASE)
    if not t or not _TOPIC_OK.match(t) or len(t.split()) > 8 or _TOPIC_BAD.search(t):
        return None
    if t.split()[0].lower() in {"you", "your", "i", "my"} and t.lower() not in {"your sister", "your brother"}:
        return None
    return t[0].lower() + t[1:] if not t[:2].isupper() else t


def not_in_plan(kind: str, topic: str | None, name: str, relation: str | None) -> tuple[str, str]:
    """(reply, pending reason). Offers contact; never advice."""
    t = clean_topic(topic or "")
    if kind == "missed_dose":
        first = "Your care plan doesn't say what to do after a missed dose."
    elif kind == "dose_interval_or_max":
        first = "Your care plan doesn't give a time between oxycodone doses or a daily limit."
    elif kind == "second_opinion":
        first = "I can't give a second opinion about your treatment."
    elif kind == "family_member":
        who = f"your {relation}" if relation else "someone else"
        first = f"I can only help with your own care plan, so I can't give advice for {who}."
    elif kind == "non_medical":
        first = "I can only help with your recovery care plan."
    elif kind == "feelings":
        return (f"I'm sorry this feels hard, {name}. "
                "Would you like me to send a message to your care team about how you're feeling?",
                "Patient shared how they are feeling")
    elif kind == "alcohol_or_cannabis":
        first = f"Your care plan doesn't cover {t}." if t else "Your care plan doesn't cover alcohol or cannabis."
    elif kind == "unlisted_medication":
        first = f"Your care plan doesn't cover {t}." if t else "Your care plan doesn't cover that medicine."
    elif kind == "other_medical":
        first = "Your care plan doesn't answer that, and I can't diagnose problems."
    else:
        first = f"Your care plan doesn't cover {t}." if t else "Your care plan doesn't cover that."
    reason = f"Question not covered by the care plan ({kind.replace('_', ' ')})"
    return f"{first} {OFFER}", reason


def refuse_dose_change(is_stop: bool) -> str:
    if is_stop:
        return ("I can't help decide whether to stop or change a medicine. "
                "Would you like me to send a message to your care team about it?")
    return f"I can't recommend changing the dose in your care plan. {OFFER}"


TRIGGER_TEXT = {
    # kind: (plan keyword that must be in the plan to say "your care plan says", plan wording, plain wording)
    "fever": ("101.5", "a fever over 101.5 F", "your fever"),
    "redness_drainage": ("redness", "increasing redness or drainage", "the redness or drainage"),
    "calf_pain_swelling": ("calf", "calf pain or swelling", "your calf"),
    "uncontrolled_pain": ("not controlled", "pain that is not controlled by medicine", "your pain"),
}
PRODUCT_TRIGGERS = {
    "fall": "Please call your medical team now to tell them about your fall.",
    "numbness_tingling_color": "Please call your medical team now about the new numbness, tingling, or color change.",
}
TRIGGER_ORDER = ("fever", "redness_drainage", "calf_pain_swelling", "uncontrolled_pain", "fall",
                 "numbness_tingling_color")


def call_surgeon(triggers: list[str], plan_text: str) -> tuple[str, str]:
    """(reply, pending reason) for a plan call trigger or a product call rule."""
    kind = next((k for k in TRIGGER_ORDER if k in triggers), "uncontrolled_pain")
    if kind in PRODUCT_TRIGGERS:
        first = PRODUCT_TRIGGERS[kind]
    else:
        keyword, plan_words, plain = TRIGGER_TEXT[kind]
        if keyword.lower() in plan_text.lower():
            first = (f"Your care plan says to call your surgeon for {plan_words}, "
                     "so please call your surgeon or medical team now.")
        else:
            first = f"Please call your surgeon or medical team now about {plain}."
    return f"{first} {OFFER_TOO}", f"Call trigger: {kind.replace('_', ' ')}"


CHECKIN_QUESTIONS = {
    "pain": "What is your pain level from zero to ten?",
    "meds_taken": "Have you taken your medicines as your care plan says?",
    "numbness": "Have you had any new numbness, tingling, or change in skin color?",
    "fall": "Have you had any falls {since}?",
}
# Follow-up after "no" or an unclear answer about medicines (one clarification, no dosing advice).
CHECKIN_CLARIFY = {
    "meds_taken": "Which medicine did you miss or feel unsure about?",
}
# Asked again when a reply does not answer the waiting question.
CHECKIN_REASK = {
    "pain": "Please tell me a number from zero to ten.",
    "meds_taken": "Have you taken all of your medicines as your care plan says, yes or no?",
    "numbness": "Have you noticed any new numbness, tingling, or color change, yes or no?",
    "fall": "Have you fallen at all, yes or no?",
}


def checkin_question(step: str, first_checkin: bool) -> str:
    since = "since your surgery" if first_checkin else "since your last check-in"
    return CHECKIN_QUESTIONS[step].format(since=since)


def operational(kind: str, name: str) -> str:
    if kind == "identity":
        return IDENTITY
    if kind == "greeting":
        return f"Hi {name}, I'm Foggy. I can explain your care plan or do a short recovery check-in."
    if kind == "thanks":
        return f"You're welcome, {name}."
    if kind == "ack":
        return "Okay. Let me know if you have a question about your care plan."
    return "I can explain your care plan, do a short check-in, or send a message to your care team's queue."


CAPABILITY = ("I can't place phone calls, but I can send a message to your care team's queue. "
              "Would you like me to do that?")


# ---- plan answers ---------------------------------------------------------------------------

def plan_answer(message: str, chunks: list[dict], history: list[dict]) -> dict | None:
    """Model answer grounded in the plan (None when no model is available)."""
    return ai_service.plan_answer(message, chunks, history)


_PT = re.compile(r"\bpt\b", re.IGNORECASE)
# Question words that name no topic ("what is my prescribed dose" is about the medicine).
_QUESTION_STEMS = {"pres", "dose", "dosa", "take", "taki", "much", "supp", "tell", "know", "mean", "info"}


def fallback_plan_answer(message: str, chunks: list[dict]) -> dict | None:
    """No model: quote the plan sentences that best match the question, or None if nothing fits."""
    question = _PT.sub("physical therapy", message)
    q_stems = set(ai_service._stems(question)) - _QUESTION_STEMS
    if not q_stems or not chunks:
        return None
    scored = []
    for ci, c in enumerate(chunks):
        for si, sentence in enumerate(split_sentences(c["content"])):
            s_stems = set(ai_service._stems(f"{sentence}"))
            score = len(q_stems & s_stems)
            if score:
                scored.append((score, ci, si, sentence, c))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    best = scored[0]
    covered = set()
    for _, _, _, sentence, _ in scored:
        covered |= q_stems & set(ai_service._stems(sentence))
    if len(covered) / len(q_stems) < 0.5:
        return None
    picked = [best]
    for cand in scored[1:]:
        if len(picked) == 2:
            break
        new_stems = (q_stems & set(ai_service._stems(cand[3]))) - (q_stems & set(ai_service._stems(best[3])))
        if new_stems or (cand[1] == best[1] and cand[0] >= best[0]):
            picked.append(cand)
    picked.sort(key=lambda x: (x[1], x[2]))
    text = " ".join(p[3] for p in picked)
    body = text[0].lower() + text[1:] if text[:2] != text[:2].upper() else text
    citations, seen = [], set()
    for p in picked:
        cid = str(p[4]["id"])
        if cid not in seen:
            seen.add(cid)
            citations.append({"chunk_id": cid, "section": p[4].get("section") or "Care plan"})
    return {"content": f"Your care plan says: {body}", "citations": citations, "answered_from_plan": True,
            "red_flag": False}
