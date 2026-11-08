"""Foggy's LLM provider layer (no network: httpx.MockTransport stands in for the APIs).

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_ai_provider.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import json
import os
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402

from app.routes.patients import split_into_chunks  # noqa: E402
from app.seed import DEMO_CARE_PLAN  # noqa: E402
from app.services import ai_service  # noqa: E402

LLM_VARS = ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_REASONING_EFFORT", "OLLAMA_URL")
TEST_KEY = "test-key-not-real"

CHUNKS = [
    {"id": uuid.uuid4(), "section": section, "content": content}
    for section, content in split_into_chunks(DEMO_CARE_PLAN)
]  # [0] Wound care, [1] Activity, [2] Pain and swelling, [3] Medications, [4] When to call


def _set_env(**values) -> None:
    """Clears every LLM variable, then sets the given ones."""
    for name in LLM_VARS:
        os.environ.pop(name, None)
    for name, value in values.items():
        os.environ[name] = value
    ai_service._ollama_probe.update(url=None, ok=False, at=0.0)
    ai_service._HTTP_TRANSPORT = None
    ai_service.RETRY_DELAY = 0.0


class _Recorder:
    """MockTransport handler that records requests and replies with canned responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


def _completion(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={
        "id": "x", "object": "chat.completion", "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
    })


def _use_gemini(*responses) -> _Recorder:
    _set_env(LLM_API_KEY=TEST_KEY)
    recorder = _Recorder(*responses)
    ai_service._HTTP_TRANSPORT = httpx.MockTransport(recorder)
    return recorder


SHOWER_JSON = json.dumps({
    "answer": "You may shower 48 hours after surgery with the waterproof dressing on.",
    "in_plan": True, "source_ids": [1], "urgent": False,
})


# ---- provider selection ----------------------------------------------------------

def test_default_is_gemini_when_key_set():
    _set_env(LLM_API_KEY=TEST_KEY)
    assert ai_service.select_provider() == "gemini"


def test_explicit_provider_wins():
    _set_env(LLM_PROVIDER="ollama", LLM_API_KEY=TEST_KEY)
    assert ai_service.select_provider() == "ollama"
    _set_env(LLM_PROVIDER="NONE", LLM_API_KEY=TEST_KEY)
    assert ai_service.select_provider() == "none"
    _set_env(LLM_PROVIDER="gemini")
    assert ai_service.select_provider() == "gemini"


def test_ollama_when_no_key_and_ollama_answers():
    _set_env(OLLAMA_URL="http://ollama.test:11434")
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"models": []})

    ai_service._HTTP_TRANSPORT = httpx.MockTransport(handler)
    assert ai_service.select_provider() == "ollama"
    assert seen == ["http://ollama.test:11434/api/tags"]
    ai_service.select_provider()
    assert len(seen) == 1, "probe result should be cached"


def test_none_when_no_key_and_ollama_unreachable():
    _set_env(OLLAMA_URL="http://ollama.test:11434")

    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    ai_service._HTTP_TRANSPORT = httpx.MockTransport(handler)
    assert ai_service.select_provider() == "none"


def test_unknown_provider_falls_back_to_auto():
    _set_env(LLM_PROVIDER="mystery", LLM_API_KEY=TEST_KEY)
    assert ai_service.select_provider() == "gemini"


def test_settings_defaults():
    _set_env()
    cfg = ai_service.llm_settings()
    assert cfg["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert cfg["model"] == ai_service.DEFAULT_LLM_MODEL
    _set_env(LLM_BASE_URL="https://llm.example.test/v1")
    assert ai_service.llm_settings()["base_url"] == "https://llm.example.test/v1/"


# ---- Gemini (OpenAI-compatible) call ----------------------------------------------

def test_gemini_answer_is_grounded_and_cited():
    recorder = _use_gemini(_completion(SHOWER_JSON))
    result = ai_service.answer_question("When can I shower?", CHUNKS, [])

    assert result == {
        "content": "You may shower 48 hours after surgery with the waterproof dressing on.",
        "citations": [{"chunk_id": str(CHUNKS[0]["id"]), "section": "Wound care"}],
        "answered_from_plan": True,
        "red_flag": False,
    }
    assert len(recorder.requests) == 1
    req = recorder.requests[0]
    assert str(req.url) == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert req.headers["authorization"] == f"Bearer {TEST_KEY}"
    body = recorder.bodies[0]
    assert body["model"] == ai_service.DEFAULT_LLM_MODEL
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["required"] == ["answer", "in_plan", "source_ids", "urgent"]
    assert body["messages"][0]["role"] == "system"
    assert "CARE PLAN:" in body["messages"][0]["content"] and "[1] Wound care:" in body["messages"][0]["content"]
    assert body["messages"][-1] == {"role": "user", "content": "When can I shower?"}


def test_history_is_passed_with_roles():
    recorder = _use_gemini(_completion(SHOWER_JSON))
    history = [{"role": "patient", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    ai_service.answer_question("When can I shower?", CHUNKS, history)
    roles = [m["role"] for m in recorder.bodies[0]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_custom_model_and_base_url():
    recorder = _Recorder(_completion(SHOWER_JSON))
    _set_env(LLM_API_KEY=TEST_KEY, LLM_BASE_URL="https://llm.example.test/v1", LLM_MODEL="some-model",
             LLM_REASONING_EFFORT="off")
    ai_service._HTTP_TRANSPORT = httpx.MockTransport(recorder)
    ai_service.answer_question("When can I shower?", CHUNKS, [])
    assert str(recorder.requests[0].url) == "https://llm.example.test/v1/chat/completions"
    assert recorder.bodies[0]["model"] == "some-model"
    assert "reasoning_effort" not in recorder.bodies[0]


def test_fenced_json_reply_is_parsed():
    _use_gemini(_completion(f"```json\n{SHOWER_JSON}\n```"))
    assert ai_service.answer_question("When can I shower?", CHUNKS, [])["answered_from_plan"] is True


def test_400_retries_without_optional_params():
    recorder = _use_gemini(httpx.Response(400, json={"error": "bad response_format"}), _completion(SHOWER_JSON))
    result = ai_service.answer_question("When can I shower?", CHUNKS, [])
    assert result["answered_from_plan"] is True
    assert len(recorder.requests) == 2
    assert "response_format" in recorder.bodies[0]
    assert "response_format" not in recorder.bodies[1] and "reasoning_effort" not in recorder.bodies[1]


def test_not_in_plan_goes_to_care_team():
    _use_gemini(_completion(json.dumps({"answer": "", "in_plan": False, "source_ids": [], "urgent": False})))
    result = ai_service.answer_question("Can I eat sushi?", CHUNKS, [])
    assert result["content"] == ai_service.NOT_IN_PLAN_REPLY
    assert result["answered_from_plan"] is False and result["citations"] == []


def test_fact_check_rejects_invented_numbers():
    invented = json.dumps({"answer": "You may shower 12 hours after surgery.", "in_plan": True,
                           "source_ids": [1], "urgent": False})
    _use_gemini(_completion(invented))
    assert ai_service.answer_question("When can I shower?", CHUNKS, [])["content"] == ai_service.NOT_IN_PLAN_REPLY


def test_fact_check_accepts_plan_wording_with_cannot():
    drive = json.dumps({"answer": "You cannot drive for 4 weeks after surgery, or while you are taking opioid "
                                  "pain medication.", "in_plan": True, "source_ids": [2], "urgent": False})
    _use_gemini(_completion(drive))
    result = ai_service.answer_question("Can I drive?", CHUNKS, [])
    assert result["answered_from_plan"] is True and result["citations"][0]["section"] == "Activity"


def test_urgent_reply_is_red_flag():
    _use_gemini(_completion(json.dumps({"answer": "", "in_plan": True, "source_ids": [5], "urgent": True})))
    result = ai_service.answer_question("My calf is swollen and hot", CHUNKS, [])
    assert result["red_flag"] is True and result["content"] == ai_service.URGENT_REPLY


def test_red_flag_never_calls_provider():
    recorder = _use_gemini(_completion(SHOWER_JSON))
    result = ai_service.answer_question("I have chest pain", CHUNKS, [])
    assert result["red_flag"] is True and result["content"] == ai_service.EMERGENCY_REPLY
    assert recorder.requests == []


# ---- fallback when the provider fails ---------------------------------------------

def _assert_keyword_fallback(result: dict) -> None:
    assert result["content"].startswith("From your care plan:"), result
    assert result["answered_from_plan"] is True
    assert result["citations"][0]["section"] == "Wound care"


def test_transient_503_is_retried_once():
    recorder = _use_gemini(httpx.Response(503, json={"error": "overloaded"}), _completion(SHOWER_JSON))
    assert ai_service.answer_question("When can I shower?", CHUNKS, [])["answered_from_plan"] is True
    assert len(recorder.requests) == 2


def test_fallback_on_server_error():
    recorder = _use_gemini(httpx.Response(503, json={"error": "overloaded"}))
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))
    assert len(recorder.requests) == 2  # first try + one retry, then keywords


def test_fallback_on_bad_key():
    _use_gemini(httpx.Response(401, json={"error": "API key not valid"}))
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))


def test_fallback_on_timeout():
    _use_gemini(httpx.ReadTimeout("slow"))
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))


def test_fallback_on_garbage_reply():
    _use_gemini(_completion("I'm not sure, sorry."))
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))


def test_explicit_gemini_without_key_falls_back_without_calling():
    _set_env(LLM_PROVIDER="gemini")
    recorder = _Recorder(_completion(SHOWER_JSON))
    ai_service._HTTP_TRANSPORT = httpx.MockTransport(recorder)
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))
    assert recorder.requests == []


def test_provider_none_uses_keywords():
    _set_env(LLM_PROVIDER="none")
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))


# ---- Ollama path is kept ----------------------------------------------------------

def test_ollama_path_still_used():
    _set_env(LLM_PROVIDER="ollama")
    calls = []
    original = ai_service._ollama_chat

    def fake_ollama(messages, schema):
        calls.append((messages, schema))
        return SHOWER_JSON

    ai_service._ollama_chat = fake_ollama
    try:
        result = ai_service.answer_question("When can I shower?", CHUNKS, [])
    finally:
        ai_service._ollama_chat = original
    assert result["answered_from_plan"] is True and result["citations"][0]["section"] == "Wound care"
    assert calls and calls[0][1] is ai_service.RESPONSE_SCHEMA


def test_ollama_unreachable_falls_back():
    _set_env(LLM_PROVIDER="ollama", OLLAMA_URL="http://127.0.0.1:9")  # discard port: refused fast
    _assert_keyword_fallback(ai_service.answer_question("When can I shower with the dressing?", CHUNKS, []))


if __name__ == "__main__":
    saved = {name: os.environ.get(name) for name in LLM_VARS}
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
