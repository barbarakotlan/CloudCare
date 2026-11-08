"""Foggy's language-model layer: grounded care-plan answers and JSON calls to the provider.

POST /chat goes through app.services.foggy (routing, state, actions; see docs/foggy-policy.md).
This module supplies the pieces it uses:
  - plan_answer(): one grounded answer from the care plan, fact-checked against the cited
    sections; None when the provider is unavailable.
  - llm_json(): a JSON-schema call to the configured provider (the router's classifier).
  - answer_question(): the original single-shot answer, kept for older callers and tests.

Safety design (Ethical AI):
  1. Red-flag keywords are checked BEFORE the LLM. Emergencies never depend on the model.
  2. The LLM may only use the patient's care plan and must cite which sections it used.
  3. A rule-based fact-check confirms every answer against the cited sections.
     If the plan doesn't cover the question, Foggy does not guess; it offers to message the care team.
  4. Nothing is sent to the care team without the patient's agreement (handled by the router).
  5. If no LLM is reachable, a simple keyword matcher is used so the app never breaks.

LLM providers (backend/.env or the host's environment):
  gemini  Google's Gemini API through its OpenAI-compatible endpoint (hosted; free tier).
          LLM_API_KEY (from https://aistudio.google.com/apikey), optional LLM_BASE_URL and
          LLM_MODEL. Any other OpenAI-compatible chat-completions API works the same way
          by pointing LLM_BASE_URL / LLM_MODEL at it.
  ollama  A local Ollama server (https://ollama.com): `ollama pull llama3.2`, keep it
          running. OLLAMA_URL, OLLAMA_MODEL. Local development only.
  none    Keyword fallback only.
LLM_PROVIDER picks one explicitly. Unset: gemini when LLM_API_KEY is set, otherwise
ollama when OLLAMA_URL answers, otherwise none.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

import httpx

log = logging.getLogger(__name__)

OLLAMA_TIMEOUT = 90  # seconds; the first request is slow while the model loads
HISTORY_TURNS = 6    # recent messages given to the model for context

DEFAULT_LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Stable Gemini Flash model on the free tier (gemini-2.5-flash is deprecated and
# closed to new API users). Check GET {LLM_BASE_URL}models for the current list.
DEFAULT_LLM_MODEL = "gemini-3.6-flash"
DEFAULT_REASONING_EFFORT = "low"  # short answers; keeps latency well under the timeout
LLM_TIMEOUT = 20.0                 # seconds, hosted provider
OLLAMA_PROBE_TIMEOUT = 1.5         # seconds, "is Ollama running?" check
OLLAMA_PROBE_TTL = 60.0            # seconds the probe result is reused
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRY_IF_UNDER = 5.0               # seconds: only retry a fast failure
RETRY_DELAY = 0.5                  # seconds

PROVIDERS = ("gemini", "ollama", "none")

# Tests swap in httpx.MockTransport here; None means real network.
_HTTP_TRANSPORT: httpx.BaseTransport | None = None
_ollama_probe: dict = {"url": None, "ok": False, "at": 0.0}


class ProviderError(Exception):
    """The LLM provider could not give a usable reply. Foggy falls back to keywords."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _ollama_url() -> str:
    return _env("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return _env("OLLAMA_MODEL", "llama3.2")


def llm_settings() -> dict:
    """Hosted provider settings, read on every call so env changes need no code change."""
    base = _env("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
    return {
        "api_key": _env("LLM_API_KEY"),
        "base_url": base if base.endswith("/") else base + "/",
        "model": _env("LLM_MODEL", DEFAULT_LLM_MODEL),
        "reasoning_effort": _env("LLM_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).lower(),
    }

# Messages containing these skip the AI entirely and escalate as an emergency.
RED_FLAGS = [
    "chest pain", "can't breathe", "cannot breathe", "trouble breathing",
    "shortness of breath", "heavy bleeding", "bleeding a lot", "fainted",
    "passed out", "unconscious", "suicidal",
]

# Policy v2 wording (docs/foggy-policy.md): nothing is sent without the patient's agreement,
# and the 911 instruction is never softened.
EMERGENCY_REPLY = "Call 911 now. I can't place emergency calls."
NOT_IN_PLAN_REPLY = (
    "Your care plan doesn't cover that, so I don't want to guess. "
    "Would you like me to send a message to your care team?"
)
URGENT_REPLY = (
    "Please call your surgeon or medical team now. "
    "Would you like me to send a message to your care team too?"
)

SYSTEM_PROMPT = """You are Foggy, an AI recovery helper for a patient recovering from surgery.
You answer ONLY using the patient's care plan sections provided below. Rules:
- Use only facts that are written in the care plan. Never add medical advice that is not in it,
  even if it is common knowledge.
- Set "in_plan" to true ONLY if a section explicitly answers the question. If the topic is not
  mentioned in the care plan, set "in_plan" to false. Guessing is never allowed.
- List the numbers of the sections you used in "source_ids".
- Set "urgent" to true if the patient describes a symptom the care plan says to call the doctor
  or 911 about, or anything that sounds dangerous.
- Write "answer" in plain, warm, simple language: one or two short sentences, about sixth-grade level.
  Start with "Your care plan says". Keep every condition, amount, frequency, duration and restriction
  the plan gives for the topic, and write numbers as digits exactly as the plan writes them.
- Restate the plan; do not add your own commentary, reassurance, or clearance. The end of a
  restriction is not permission ("no driving for 4 weeks" does not mean "you can drive after 4 weeks").
- Never recommend changing a medicine, and never invent timing, limits, or missed-dose instructions.
- Do not mention section numbers in the answer text. No lists or Markdown.
Respond with JSON only.

Examples (for a different care plan that covers wound care and activity, but not diet or travel):
Q: "Can I go swimming?"   (plan says: no pools for 4 weeks)
-> {"answer": "Your care plan says no pools for 4 weeks.", "in_plan": true, "source_ids": [1], "urgent": false}
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
yes no not cannot yet still just only also too very really some any all much many more most
often long again ever now today tonight tomorrow time times back okay ok fine good sure
please need want try stay keep avoid wait allowed safe let lets like after before until
day days week weeks while during each every per around about normal without
surgery operation procedure doctor team care plan
says say said both even either neither nor unless
""".split())

# Question words that name no topic ("what is my prescribed dose?" is about the medicine).
# Ignored by the topic check only; an answer still may not add them as new facts.
TOPIC_NEUTRAL_STEMS = {"pres", "dose", "dosa", "much", "tell", "know", "mean"}

# Contractions -> plain words, so "don't" checks as "do not" (both carry the same facts).
CONTRACTIONS = (
    (re.compile(r"\bcan['’]t\b"), "can not"), (re.compile(r"\bwon['’]t\b"), "will not"),
    (re.compile(r"n['’]t\b"), " not"), (re.compile(r"['’](re|ve|ll|d|m|s)\b"), ""),
)

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
    text = text.lower()
    for pattern, repl in CONTRACTIONS:
        text = pattern.sub(repl, text)
    for w in re.findall(r"[a-z]+", text):
        if w in FILLER_WORDS or len(w) < 3:
            continue
        w = SYNONYMS.get(w, w)
        out.append(w[:4])
    return out

# Structured outputs (Ollama `format`, OpenAI-compatible `response_format`): forces the
# model to reply in exactly this JSON shape.
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
    """Stateless single-shot answer (no conversation state, no actions). POST /chat uses
    app.services.foggy.answer_turn instead; this stays for older callers and tests.

    Inputs:
      message: the patient's question
      chunks:  this patient's care plan pieces, each {"id", "section", "content"}
      history: recent chat, each {"role", "content"} (oldest first)

    Returns a dict:
      {
        "content": str,                 # Foggy's reply
        "citations": [{"chunk_id": str, "section": str}],
        "answered_from_plan": bool,     # False -> the plan does not cover it
        "red_flag": bool,               # True  -> possible emergency
      }
    """
    if is_red_flag(message):
        return _reply(EMERGENCY_REPLY, red_flag=True)
    if not chunks:
        return _reply(NOT_IN_PLAN_REPLY)

    provider = select_provider()
    if provider != "none":
        try:
            return _answer_with_llm(provider, message, chunks, history)
        except ProviderError as e:
            log.warning("LLM provider=%s unavailable (%s). Using keyword fallback.", provider, e)
        except (urllib.error.URLError, TimeoutError, ConnectionError, httpx.HTTPError) as e:
            log.warning(
                "LLM provider=%s not reachable (%s). Using keyword fallback.", provider, type(e).__name__
            )
        except Exception as e:  # noqa: BLE001  (a model problem must never break chat)
            log.warning("LLM provider=%s failed (%s). Using keyword fallback.", provider, type(e).__name__)
    return answer_with_keywords(message, chunks)


def plan_answer(message: str, chunks: list[dict], history: list[dict]) -> dict | None:
    """One grounded answer from the care plan for the router's ANSWER_FROM_PLAN route.

    Returns the same dict as answer_question() (answered_from_plan False when the plan does
    not cover it or the fact-check rejects the answer), or None when no provider is
    configured or it failed, so the caller can use its own fallback. The model's "urgent"
    flag is ignored here: the router has already decided the route.
    """
    if not chunks:
        return _reply(NOT_IN_PLAN_REPLY)
    provider = select_provider()
    if provider == "none":
        return None
    try:
        messages = _build_messages(message, chunks, history)
        if provider == "ollama":
            raw = _ollama_chat(messages, RESPONSE_SCHEMA)
        else:
            raw = _openai_compatible_chat(provider, messages, RESPONSE_SCHEMA)
        return _checked_reply(message, chunks, _parse_json(raw), honor_urgent=False)
    except Exception as e:  # noqa: BLE001  (a model problem must never break chat)
        log.warning("LLM provider=%s plan answer failed (%s).", provider, type(e).__name__)
        return None


def llm_json(messages: list[dict], schema: dict, name: str) -> dict:
    """JSON-schema call to the configured provider. Raises ProviderError when there is none
    or the call fails; callers fall back to rules."""
    provider = select_provider()
    if provider == "none":
        raise ProviderError("no provider configured")
    try:
        if provider == "ollama":
            raw = _ollama_chat(messages, schema)
        else:
            raw = _openai_compatible_chat(provider, messages, schema, name=name)
    except ProviderError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ProviderError(type(e).__name__) from None
    return _parse_json(raw)


# ---- Provider selection -------------------------------------------------------

def select_provider() -> str:
    """'gemini' | 'ollama' | 'none'.

    LLM_PROVIDER wins when set. Otherwise: gemini if LLM_API_KEY is set, else ollama if
    OLLAMA_URL answers, else none (keyword fallback).
    """
    choice = _env("LLM_PROVIDER").lower()
    if choice in ("openai", "openai-compatible"):
        choice = "gemini"  # same request shape; LLM_BASE_URL decides where it goes
    if choice in PROVIDERS:
        return choice
    if choice:
        log.warning("Unknown LLM_PROVIDER=%r; choosing automatically.", choice)
    if _env("LLM_API_KEY"):
        return "gemini"
    if ollama_reachable():
        return "ollama"
    return "none"


def ollama_reachable() -> bool:
    """Quick check that an Ollama server answers at OLLAMA_URL. Cached for a minute."""
    url = _ollama_url()
    now = time.monotonic()
    if _ollama_probe["url"] == url and now - _ollama_probe["at"] < OLLAMA_PROBE_TTL:
        return _ollama_probe["ok"]
    try:
        with httpx.Client(timeout=OLLAMA_PROBE_TIMEOUT, transport=_HTTP_TRANSPORT) as client:
            ok = client.get(f"{url}/api/tags").status_code == 200
    except httpx.HTTPError:
        ok = False
    _ollama_probe.update(url=url, ok=ok, at=now)
    return ok


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


# ---- LLM answer (any provider) -------------------------------------------------

def _build_messages(message: str, chunks: list[dict], history: list[dict]) -> list[dict]:
    plan_text = "\n\n".join(
        f"[{i}] {c.get('section') or 'Care plan'}:\n{c['content']}" for i, c in enumerate(chunks, start=1)
    )
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCARE PLAN:\n{plan_text}"}]
    for h in history[-HISTORY_TURNS:]:
        messages.append({"role": "user" if h["role"] == "patient" else "assistant", "content": h["content"]})
    messages.append({"role": "user", "content": message})
    return messages


def _answer_with_llm(provider: str, message: str, chunks: list[dict], history: list[dict]) -> dict:
    messages = _build_messages(message, chunks, history)
    if provider == "ollama":
        raw = _ollama_chat(messages, RESPONSE_SCHEMA)
    else:
        raw = _openai_compatible_chat(provider, messages, RESPONSE_SCHEMA)
    return _checked_reply(message, chunks, _parse_json(raw))


def _answer_with_ollama(message: str, chunks: list[dict], history: list[dict]) -> dict:
    return _answer_with_llm("ollama", message, chunks, history)


def _parse_json(raw: str) -> dict:
    """The model's JSON reply. Tolerates ```json fences or text around the object."""
    text = (raw or "").strip()
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ProviderError("reply was not JSON") from None
        try:
            data = json.loads(text[start:end + 1])
        except ValueError:
            raise ProviderError("reply was not JSON") from None
    if not isinstance(data, dict):
        raise ProviderError("reply was not a JSON object")
    return data


def _checked_reply(message: str, chunks: list[dict], data: dict, honor_urgent: bool = True) -> dict:
    """Turns the model's JSON into Foggy's reply, keeping only grounded answers."""
    if honor_urgent and data.get("urgent"):
        return _reply(URGENT_REPLY, red_flag=True)

    used = [chunks[i - 1] for i in data.get("source_ids", []) if isinstance(i, int) and 1 <= i <= len(chunks)]
    answer = (data.get("answer") or "").strip()

    # Only trust an answer that the model says is in the plan AND that cites a real section...
    if not data.get("in_plan") or not used or not answer:
        return _reply(NOT_IN_PLAN_REPLY)

    # ...AND that passes a rule-based fact-check against those sections.
    if not _is_grounded(message, answer, used):
        log.info("Fact-check rejected an answer; sending the question to the care team.")
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
    topic_stems = question_stems - TOPIC_NEUTRAL_STEMS
    if topic_stems:
        covered = sum(1 for s in topic_stems if s in source_stems)
        if covered / len(topic_stems) < 0.5:
            return False

    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source))
    if any(n not in source_numbers for n in re.findall(r"\d+(?:\.\d+)?", answer)):
        return False

    allowed = source_stems | question_stems
    return all(s in allowed for s in _stems(answer))


# ---- Providers ----------------------------------------------------------------

def _ollama_chat(messages: list[dict], schema: dict) -> str:
    body = json.dumps({
        "model": _ollama_model(),
        "messages": messages,
        "format": schema,
        "stream": False,
        "options": {"temperature": 0},  # consistent, factual answers
    }).encode()
    req = urllib.request.Request(
        f"{_ollama_url()}/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
        log.info("LLM provider=ollama status=%s", resp.status)
        return json.loads(resp.read())["message"]["content"]


def _openai_compatible_chat(provider: str, messages: list[dict], schema: dict, name: str = "foggy_answer") -> str:
    """POST {LLM_BASE_URL}chat/completions (Gemini's OpenAI-compatible API by default).

    Asks for JSON matching `schema`. If the provider rejects the optional parameters
    (HTTP 400), retries once without them and parses the JSON out of the text instead.
    """
    cfg = llm_settings()
    if not cfg["api_key"]:
        raise ProviderError("LLM_API_KEY is not set")

    strict_schema = {**schema, "additionalProperties": False}
    body: dict = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0,  # consistent, factual answers
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": strict_schema},
        },
    }
    if cfg["reasoning_effort"] not in ("", "off"):
        body["reasoning_effort"] = cfg["reasoning_effort"]

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    started = time.monotonic()
    with httpx.Client(
        base_url=cfg["base_url"], headers=headers, timeout=LLM_TIMEOUT, transport=_HTTP_TRANSPORT
    ) as client:
        res = client.post("chat/completions", json=body)
        log.info("LLM provider=%s status=%s", provider, res.status_code)
        if res.status_code == 400:
            body.pop("response_format", None)
            body.pop("reasoning_effort", None)
            res = client.post("chat/completions", json=body)
            log.info("LLM provider=%s retry=plain status=%s", provider, res.status_code)
        # Busy or rate-limited: one quick retry if there is time left.
        if res.status_code in RETRY_STATUSES and time.monotonic() - started < RETRY_IF_UNDER:
            time.sleep(RETRY_DELAY)
            res = client.post("chat/completions", json=body)
            log.info("LLM provider=%s retry=transient status=%s", provider, res.status_code)

    if not res.is_success:
        raise ProviderError(f"HTTP {res.status_code}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("unexpected response shape") from None
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("empty reply")
    return content


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
