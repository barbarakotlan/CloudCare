"""Phone calls from Foggy through ElevenLabs Agents' Twilio outbound-call API.

POST {ELEVENLABS_API_BASE}/v1/convai/twilio/outbound-call, header `xi-api-key`, JSON
{agent_id, agent_phone_number_id, to_number, telephony_call_config, conversation_initiation_client_data}
(https://elevenlabs.io/docs/api-reference/twilio/outbound-call).
The reply is 200 {success, message, conversation_id, callSid}; success=true means
Twilio started dialing. It does not mean the patient answered.

The call carries the same dynamic variables the browser voice session sends, so the
agent's `ask_cloudcare` tool reaches /chat as this patient. The token in
`secret__patient_auth` is a CloudCare token made for this call only (30 minutes);
ElevenLabs keeps secret__ variables out of the model's prompt and redacts them in
stored conversations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.auth import sign_local_token
from app.models import User
from app.outreach.config import OutreachSettings, http_client

log = logging.getLogger("cloudcare.outreach")

CALL_TOKEN_MINUTES = 30
GENERIC_FAILURE = "I couldn't start the call. Please try again later or call your medical team."


@dataclass(frozen=True)
class CallResult:
    ok: bool
    conversation_id: str | None = None
    call_sid: str | None = None
    detail: str | None = None


def call_token(user: User) -> str:
    """Short-lived CloudCare bearer token for the agent's tools during one call."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "purpose": "phone_call",
        "iat": now,
        "exp": now + timedelta(minutes=CALL_TOKEN_MINUTES),
    }
    # Raises LocalTokensDisabled in production without a strong JWT_SECRET (router checks first).
    return sign_local_token(payload)


def first_name(full_name: str | None) -> str:
    first = (full_name or "").strip().split(" ")[0] if full_name else ""
    return first[:40] or "there"


def telephony_call_config(settings: OutreachSettings) -> dict:
    """`telephony_call_config` for the outbound-call request.

    ringing_timeout_secs: how long the phone rings before Twilio gives up.

    twilio_machine_detection: Twilio answering-machine detection (AMD). Mode "enable" gives a
    quick human / machine verdict and does not delay the start of the conversation. The verdict
    is reported to ElevenLabs as an `answering_machine_detection` webhook event (turn that event
    on in the workspace or agent webhook settings to see it per call).

    Why machine verdicts never hang up: iPhone Call Screening (and Google's Call Screen on
    Android) answers calls from unknown numbers with an automated assistant that asks who is
    calling and why, then shows the patient a live transcript so they can decide to pick up.
    Twilio classifies that assistant as a machine. Hanging up on it would drop exactly the calls
    the patient would accept once they hear it is their care team, so Foggy answers the screener
    itself (says it is calling from the care team for a recovery check-in and waits for a real
    greeting), and on a real voicemail leaves one sentence and ends the call. Only fax lines,
    where no person can ever answer, are hung up on.
    """
    config: dict = {"ringing_timeout_secs": settings.ringing_timeout_secs}
    if settings.machine_detection:
        config["twilio_machine_detection"] = {
            "mode": "enable",
            "actions": [{"action": "hang_up", "answered_by": ["fax"]}],
        }
    return config


def build_payload(settings: OutreachSettings, user: User, to_number: str) -> dict:
    return {
        "agent_id": settings.elevenlabs_agent_id,
        "agent_phone_number_id": settings.elevenlabs_phone_number_id,
        "to_number": to_number,
        "telephony_call_config": telephony_call_config(settings),
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "patient_name": first_name(user.full_name),
                "patient_mode": "signed_in",
                "secret__patient_auth": f"Bearer {call_token(user)}",
            },
        },
    }


def _error_detail(status_code: int, data: object) -> str:
    if status_code == 401:
        return "The calling service rejected the server's ElevenLabs key."
    if status_code == 404:
        return "The calling service couldn't find the agent or phone number set on this server."
    if status_code == 422:
        return "The calling service didn't accept the call request."
    if status_code == 429:
        return "The calling service is busy. Please try again in a minute."
    return GENERIC_FAILURE


def start_call(settings: OutreachSettings, user: User, to_number: str) -> CallResult:
    url = f"{settings.elevenlabs_api_base}/v1/convai/twilio/outbound-call"
    headers = {"xi-api-key": settings.elevenlabs_api_key, "Accept": "application/json"}
    try:
        with http_client() as client:
            res = client.post(url, json=build_payload(settings, user, to_number), headers=headers)
    except httpx.HTTPError as exc:
        log.warning("outreach.call.network_error type=%s", type(exc).__name__)
        return CallResult(ok=False, detail="I couldn't reach the calling service. Please try again in a minute.")

    try:
        data = res.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    if res.status_code == 200 and data.get("success") is True:
        conversation_id = data.get("conversation_id") if isinstance(data.get("conversation_id"), str) else None
        call_sid = data.get("callSid") if isinstance(data.get("callSid"), str) else None
        log.info("outreach.call.started http=200 conversation=%s", bool(conversation_id))
        return CallResult(ok=True, conversation_id=conversation_id, call_sid=call_sid)

    if res.status_code == 200:
        # success=false: ElevenLabs reached Twilio but Twilio refused (e.g. trial account,
        # unverified destination, number without voice). The message is Twilio's wording.
        log.warning("outreach.call.refused http=200")
        message = data.get("message") if isinstance(data.get("message"), str) else ""
        detail = GENERIC_FAILURE
        if "unverified" in message.lower() or "trial" in message.lower():
            detail = "The server's Twilio trial account can only call numbers verified in Twilio."
        return CallResult(ok=False, detail=detail)

    log.warning("outreach.call.failed http=%s", res.status_code)
    return CallResult(ok=False, detail=_error_detail(res.status_code, data))
