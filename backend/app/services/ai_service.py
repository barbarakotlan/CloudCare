"""Foggy: answers patient questions ONLY from their care plan, using a local Ollama LLM.

Safety design (Ethical AI):
  1. Red-flag keywords are checked BEFORE the LLM. Emergencies never depend on the model.
  2. The LLM may only use the patient's care plan and must cite which sections it used.
  3. A rule-based fact-check confirms every answer against the cited sections.
     If the plan doesn't cover the question, Foggy does not guess. The question goes to the care team.
  4. The LLM can also mark a message as urgent, which escalates it like a red flag.
  5. If Ollama isn't running, a simple keyword matcher is used so the app never breaks.

Setup: install Ollama (https://ollama.com), run `ollama pull llama3.2`, keep Ollama running.
Config (backend/.env): OLLAMA_URL, OLLAMA_MODEL.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = 90  # seconds; the first request is slow while the model loads
HISTORY_TURNS = 6    # recent messages given to the model for context

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
URGENT_REPLY = (
    "That could need prompt medical attention. Please call your surgeon's office now, "
    "or 911 if it feels severe. I've also alerted your care team."
)

SYSTEM_PROMPT = """You are Foggy, a friendly recovery assistant for a patient recovering from surgery.
You answer ONLY using the patient's care plan sections provided below. Rules:
- Use only facts that are written in the care plan. Never add medical advice that is not in it,
  even if it is common knowledge.
- Set "in_plan" to true ONLY if a section explicitly answers the question. If the topic is not
  mentioned in the care plan, set "in_plan" to false. Guessing is never allowed.
- List the numbers of the sections you used in "source_ids".
- Set "urgent" to true if the patient describes a symptom the care plan says to call the doctor
  or 911 about, or anything that sounds dangerous.
- Write "answer" in plain, warm, simple language (1-3 sentences). The patient may be tired or on medication.
- Do not mention section numbers in the answer text.
Respond with JSON only.

Examples (for a different care plan that covers wound care and activity, but not diet or travel):
Q: "Can I go swimming?"   (plan says: no pools for 4 weeks)
-> {"answer": "Not yet. Please stay out of pools for 4 weeks.", "in_plan": true, "source_ids": [1], "urgent": false}
Q: "Can I eat spicy food?"   (plan never mentions food)
-> {"answer": "", "in_plan": false, "source_ids": [], "urgent": false}
Q: "Is it OK to fly next week?"   (plan never mentions flying or travel)
-> {"answer": "", "in_plan": false, "source_ids": [], "urgent": false}"""

# ---- Fact-check vocabulary (used by _is_grounded) ---------------------------
# Everyday words that carry no medical facts. They may appear in a question or answer freely.
FILLER_WORDS = set("""
a an the and or but if so to of in on at for with from by about as into than then
i im me my you your youre we our it its is are was were be been being am do does did done
can could should would will may might must shall have has had get gets got go goes going
how what when where why who which whom whose there here this that these those
yes no not yet still just only also too very really some any all much many more most
often long again ever now today tonight tomorrow time times back okay ok fine good sure
please need want try stay keep avoid wait allowed safe let lets like after before until
day days week weeks while during each every per around about normal without
surgery operation procedure doctor team care plan
""".split())

# Common patient words -> the word the care plan is likely to use.
SYNONYMS = {
    "tylenol": "acetaminophen", "paracetamol": "acetaminophen",
    "oxy": "oxycodone", "percocet": "oxycodone", "painkiller": "pain", "painkillers": "pain",
    "swollen": "swelling", "swell": "swelling", "puffy": "swelling",
    "bathe": "bath", "bathing": "bath", "tub": "bath", "swim": "pool", "swimming": "pool",
    "car": "driving", "temperature": "fever", "temp": "fever",
    "bandage": "dressing", "cut": "incision", "wound": "incision", "stitches": "incision",
}


def _stems(text: str) -> list[str]:
    """Lowercase words -> rough stems (first 4 letters), with synonyms applied. 'driving' ~ 'drive'."""
    out = []
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in FILLER_WORDS or len(w) < 3:
            continue
        w = SYNONYMS.get(w, w)
        out.append(w[:4])
    return out

# Ollama "structured outputs": forces the model to reply in exactly this JSON shape.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "in_plan": {"type": "boolean"},
        "source_ids": {"type": "array", "items": {"type": "integer"}},
        "urgent": {"type": "boolean"},
    },
    "required": ["answer", "in_plan", "source_ids", "urgent"],
}


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
    if is_red_flag(message):
        return _reply(EMERGENCY_REPLY, red_flag=True)
    if not chunks:
        return _reply(NOT_IN_PLAN_REPLY)

    try:
        return _answer_with_ollama(message, chunks, history)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        log.warning("Ollama not reachable at %s (%s). Using keyword fallback.", OLLAMA_URL, e)
    except Exception:
        log.exception("Ollama answer failed. Using keyword fallback.")
    return answer_with_keywords(message, chunks)


def is_red_flag(message: str) -> bool:
    text = message.lower()
    return any(flag in text for flag in RED_FLAGS)


def _reply(content: str, citations=None, answered_from_plan=False, red_flag=False) -> dict:
    return {
        "content": content,
        "citations": citations or [],
        "answered_from_plan": answered_from_plan,
        "red_flag": red_flag,
    }


# ---- Ollama -----------------------------------------------------------------

def _answer_with_ollama(message: str, chunks: list[dict], history: list[dict]) -> dict:
    plan_text = "\n\n".join(
        f"[{i}] {c.get('section') or 'Care plan'}:\n{c['content']}" for i, c in enumerate(chunks, start=1)
    )
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCARE PLAN:\n{plan_text}"}]
    for h in history[-HISTORY_TURNS:]:
        messages.append({"role": "user" if h["role"] == "patient" else "assistant", "content": h["content"]})
    messages.append({"role": "user", "content": message})

    data = json.loads(_ollama_chat(messages, RESPONSE_SCHEMA))

    if data.get("urgent"):
        return _reply(URGENT_REPLY, red_flag=True)

    used = [chunks[i - 1] for i in data.get("source_ids", []) if isinstance(i, int) and 1 <= i <= len(chunks)]
    answer = (data.get("answer") or "").strip()

    # Only trust an answer that the model says is in the plan AND that cites a real section...
    if not data.get("in_plan") or not used or not answer:
        return _reply(NOT_IN_PLAN_REPLY)

    # ...AND that passes a rule-based fact-check against those sections.
    if not _is_grounded(message, answer, used):
        log.info("Fact-check rejected answer %r to %r", answer, message)
        return _reply(NOT_IN_PLAN_REPLY)

    citations = [{"chunk_id": str(c["id"]), "section": c.get("section") or "Care plan"} for c in used]
    return _reply(answer, citations=citations, answered_from_plan=True)


def _is_grounded(question: str, answer: str, used: list[dict]) -> bool:
    """Rule-based fact-check: is the answer really backed by the cited care plan text?

    (A second LLM call was tried for this, but small local models judged it unreliably.)
      1. Topic check: at least half of the question's key words appear in the cited text.
         Stops "cited a real section that doesn't cover this topic" (e.g. wine -> Medications).
      2. No new facts: every number, and every meaningful word in the answer, appears in the
         cited text or the question. Stops invented rules like "no alcohol for 4 weeks".
    """
    source = " ".join(f"{c.get('section') or ''} {c['content']}" for c in used)
    source_stems = set(_stems(source))

    question_stems = set(_stems(question))
    if question_stems:
        covered = sum(1 for s in question_stems if s in source_stems)
        if covered / len(question_stems) < 0.5:
            return False

    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source))
    if any(n not in source_numbers for n in re.findall(r"\d+(?:\.\d+)?", answer)):
        return False

    allowed = source_stems | question_stems
    return all(s in allowed for s in _stems(answer))


def _ollama_chat(messages: list[dict], schema: dict) -> str:
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "format": schema,
        "stream": False,
        "options": {"temperature": 0},  # consistent, factual answers
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
        return json.loads(resp.read())["message"]["content"]


# ---- Fallback (no LLM) ------------------------------------------------------

def answer_with_keywords(message: str, chunks: list[dict]) -> dict:
    """Picks the care plan section sharing the most words with the question."""
    words = {w for w in re.findall(r"[a-z']+", message.lower()) if len(w) > 3}
    best, best_hits = None, 0
    for c in chunks:
        haystack = f"{c.get('section') or ''} {c['content']}".lower()
        hits = sum(1 for w in words if w in haystack)
        if hits > best_hits:
            best, best_hits = c, hits

    if best is None:
        return _reply(NOT_IN_PLAN_REPLY)
    return _reply(
        f"From your care plan: {best['content']}",
        citations=[{"chunk_id": str(best["id"]), "section": best.get("section") or "Care plan"}],
        answered_from_plan=True,
    )
