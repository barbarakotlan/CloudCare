"""Texts through Twilio's Messages REST API (httpx, HTTP Basic auth, no SDK).

POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json
form fields To, From (or MessagingServiceSid), Body. A 201 with status queued/accepted
means Twilio accepted the text for delivery; it does not mean the phone received it.
Carrier-side failures (unregistered 10DLC, for example) show up later on the message's
status, which `fetch_status` reads.
"""

import logging
from dataclasses import dataclass

import httpx

from app.outreach.config import TWILIO_API_BASE, OutreachSettings, http_client

log = logging.getLogger("cloudcare.outreach")

MAX_BODY_CHARS = 320  # two GSM-7 segments

# Twilio error codes a patient or the person running the demo can act on.
# https://www.twilio.com/docs/api/errors
_TWILIO_ERRORS = {
    21211: "That mobile number isn't valid. Check it and try again.",
    21408: "Texting to this country isn't turned on for this CloudCare server.",
    21610: "This number replied STOP, so texts are blocked. Reply START from your phone to allow them again.",
    21612: "Twilio can't send texts to this number from CloudCare's number.",
    21614: "That number can't receive texts. Use a mobile number.",
    21606: "CloudCare's sending number can't send texts. The server's Twilio number needs SMS turned on.",
    21608: "This server uses a Twilio trial account, which can only text numbers verified in Twilio.",
    21659: "CloudCare's sending number isn't a Twilio number on this account.",
    20003: "The server's Twilio credentials were rejected.",
    30034: "The carrier blocked the text because CloudCare's US number isn't registered for business texting (A2P 10DLC) yet.",
    30032: "The carrier blocked the text because CloudCare's toll-free number isn't verified yet.",
    30003: "Your phone was unreachable. Check that it's on and has signal.",
    30005: "The carrier says this number doesn't exist or can't receive texts.",
    30006: "This number can't receive texts (it may be a landline).",
    30007: "The carrier filtered the text.",
}

GENERIC_FAILURE = "I couldn't send the text. Please try again later or call your medical team."


def explain_error(code: int | None) -> str:
    if code is None:
        return GENERIC_FAILURE
    return _TWILIO_ERRORS.get(int(code), f"I couldn't send the text (Twilio error {code}).")


@dataclass(frozen=True)
class SmsResult:
    ok: bool
    provider_id: str | None = None
    provider_status: str | None = None
    error_code: int | None = None
    detail: str | None = None


def _first_name(full_name: str | None) -> str:
    first = (full_name or "").strip().split(" ")[0] if full_name else ""
    # Keep the text inside the GSM-7 alphabet and short; drop anything unusual.
    first = "".join(ch for ch in first if ch.isascii() and (ch.isalpha() or ch in "-'"))[:20]
    return first or "there"


def build_body(kind: str, full_name: str | None, app_url: str, plan_sections: list[str] | None = None) -> str:
    """Plain-language text, ASCII only, at most 320 characters, always with the dashboard link."""
    name = _first_name(full_name)
    dashboard = f"{app_url}/patient/dashboard"
    footer = " For chest pain or trouble breathing, call 911. Reply STOP to opt out."
    if kind == "plan_summary":
        sections = [s.strip() for s in (plan_sections or []) if s and s.strip()]
        sections = ["".join(ch for ch in s if ch.isascii())[:30] for s in sections]
        if sections:
            head = f"Hi {name}, it's Foggy from CloudCare. Your care plan covers: "
            tail = f". Read it any time: {dashboard}"
            listed: list[str] = []
            for section in sections:
                candidate = ", ".join(listed + [section])
                if len(head + candidate + tail + footer) > MAX_BODY_CHARS:
                    break
                listed.append(section)
            body = head + ", ".join(listed) + tail + footer
        else:
            body = (
                f"Hi {name}, it's Foggy from CloudCare. Your care team hasn't added your care plan yet. "
                f"Check here: {dashboard}" + footer
            )
    else:  # checkin
        body = (
            f"Hi {name}, it's Foggy from CloudCare. Time for your recovery check-in. "
            f"It takes about a minute: {dashboard}#check-in" + footer
        )
    if len(body) > MAX_BODY_CHARS:  # only possible with a very long app URL
        body = body[:MAX_BODY_CHARS]
    return body


def _auth(settings: OutreachSettings) -> httpx.BasicAuth:
    return httpx.BasicAuth(settings.twilio_account_sid, settings.twilio_auth_token)


def send_sms(settings: OutreachSettings, to_number: str, body: str) -> SmsResult:
    url = f"{TWILIO_API_BASE}/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    form = {"To": to_number, "Body": body}
    if settings.twilio_messaging_service_sid:
        form["MessagingServiceSid"] = settings.twilio_messaging_service_sid
    else:
        form["From"] = settings.twilio_from_number
    try:
        with http_client() as client:
            res = client.post(url, data=form, auth=_auth(settings), headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        log.warning("outreach.sms.network_error type=%s", type(exc).__name__)
        return SmsResult(ok=False, detail="I couldn't reach the texting service. Please try again in a minute.")

    try:
        data = res.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    if res.status_code in (200, 201):
        status = str(data.get("status") or "")
        sid = data.get("sid") if isinstance(data.get("sid"), str) else None
        if status in ("failed", "undelivered") or data.get("error_code"):
            code = data.get("error_code")
            log.warning("outreach.sms.rejected http=%s code=%s", res.status_code, code)
            return SmsResult(ok=False, provider_id=sid, provider_status=status, error_code=code, detail=explain_error(code))
        log.info("outreach.sms.accepted http=%s status=%s", res.status_code, status or "-")
        return SmsResult(ok=True, provider_id=sid, provider_status=status or "queued")

    code = data.get("code") if isinstance(data.get("code"), int) else None
    log.warning("outreach.sms.failed http=%s code=%s", res.status_code, code)
    return SmsResult(ok=False, error_code=code, detail=explain_error(code))


def fetch_status(settings: OutreachSettings, message_sid: str) -> SmsResult:
    """Reads a message's current delivery status (queued, sent, delivered, undelivered, failed...)."""
    url = f"{TWILIO_API_BASE}/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages/{message_sid}.json"
    try:
        with http_client() as client:
            res = client.get(url, auth=_auth(settings), headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        log.warning("outreach.sms.status.network_error type=%s", type(exc).__name__)
        return SmsResult(ok=False, provider_id=message_sid, detail="Couldn't check the text's status right now.")
    if res.status_code != 200:
        log.warning("outreach.sms.status.failed http=%s", res.status_code)
        return SmsResult(ok=False, provider_id=message_sid, detail="Couldn't check the text's status right now.")
    try:
        data = res.json()
    except ValueError:
        data = {}
    status = str(data.get("status") or "unknown") if isinstance(data, dict) else "unknown"
    code = data.get("error_code") if isinstance(data, dict) else None
    failed = status in ("failed", "undelivered")
    return SmsResult(
        ok=not failed,
        provider_id=message_sid,
        provider_status=status,
        error_code=code if failed else None,
        detail=explain_error(code) if failed else None,
    )
