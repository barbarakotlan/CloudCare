"""Foggy: answers patient questions from their care plan.

>>> PLACEHOLDER (owned by Person 3 / AI) <<<
This keyword-matching version exists only so the chat endpoint works end to end.
Replace the body of answer_question() with the real LLM + retrieval logic, but
KEEP THE SAME INPUTS AND OUTPUT so backend/app/routes/chat.py keeps working.
"""

import re

# Messages containing these skip the AI entirely and escalate as an emergency.
RED_FLAGS = [
    "chest pain", "can't breathe", "cannot breathe", "trouble breathing",
    "shortness of breath", "heavy bleeding", "bleeding a lot", "fainted",
    "passed out", "unconscious", "suicidal",
]

EMERGENCY_REPLY = (
    "What you're describing can be an emergency. Please call 911 now. "
    "I've also alerted your care team."
)
NOT_IN_PLAN_REPLY = (
    "I don't see that in your care plan, so I don't want to guess. "
    "I've sent your question to your care team, and they'll get back to you."
)


def answer_question(message: str, chunks: list[dict], history: list[dict]) -> dict:
    """
    Inputs:
      message: the patient's question
      chunks:  this patient's care plan pieces, each {"id", "section", "content"}
      history: recent chat, each {"role", "content"} (oldest first)

    Returns a dict:
      {
        "content": str,                 # Foggy's reply
        "citations": [{"chunk_id": str, "section": str}],
        "answered_from_plan": bool,     # False -> escalated as unanswered_question
        "red_flag": bool,               # True  -> escalated as emergency
      }
    """
    text = message.lower()

    if any(flag in text for flag in RED_FLAGS):
        return {"content": EMERGENCY_REPLY, "citations": [], "answered_from_plan": False, "red_flag": True}

    words = {w for w in re.findall(r"[a-z']+", text) if len(w) > 3}
    best, best_hits = None, 0
    for c in chunks:
        haystack = f"{c.get('section') or ''} {c['content']}".lower()
        hits = sum(1 for w in words if w in haystack)
        if hits > best_hits:
            best, best_hits = c, hits

    if best is None:
        return {"content": NOT_IN_PLAN_REPLY, "citations": [], "answered_from_plan": False, "red_flag": False}

    return {
        "content": f"From your care plan: {best['content']}",
        "citations": [{"chunk_id": str(best["id"]), "section": best.get("section") or "Care plan"}],
        "answered_from_plan": True,
        "red_flag": False,
    }
