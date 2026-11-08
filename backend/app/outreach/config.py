"""Outreach settings (Twilio texts, ElevenLabs phone calls) and the shared HTTP client.

Read from the environment at call time, so a missing value shows up as a clear
"not configured" state on /outreach/* instead of a crash at import. Setup steps for
each dashboard: docs/phone-outreach.md.
"""

import os
from dataclasses import dataclass

import httpx

TWILIO_API_BASE = "https://api.twilio.com"
ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
DEFAULT_PUBLIC_APP_URL = "https://cloudcare.icu"

# Twilio answers in well under a second; ElevenLabs starts the Twilio call before replying.
HTTP_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

SMS_INTERVAL_SECONDS = 60
CALL_INTERVAL_SECONDS = 120


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class OutreachSettings:
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    twilio_messaging_service_sid: str
    elevenlabs_api_key: str
    elevenlabs_agent_id: str
    elevenlabs_phone_number_id: str
    elevenlabs_api_base: str
    public_app_url: str
    # Country calling codes CloudCare may text or call, e.g. ("1",). Empty = any.
    allowed_country_codes: tuple[str, ...]

    @property
    def sms_missing(self) -> list[str]:
        out = []
        if not self.twilio_account_sid:
            out.append("TWILIO_ACCOUNT_SID")
        if not self.twilio_auth_token:
            out.append("TWILIO_AUTH_TOKEN")
        if not (self.twilio_from_number or self.twilio_messaging_service_sid):
            out.append("TWILIO_FROM_NUMBER")
        return out

    @property
    def call_missing(self) -> list[str]:
        out = []
        if not self.elevenlabs_api_key:
            out.append("ELEVENLABS_API_KEY")
        if not self.elevenlabs_agent_id:
            out.append("ELEVENLABS_AGENT_ID")
        if not self.elevenlabs_phone_number_id:
            out.append("ELEVENLABS_PHONE_NUMBER_ID")
        return out

    @property
    def sms_configured(self) -> bool:
        return not self.sms_missing

    @property
    def call_configured(self) -> bool:
        return not self.call_missing

    def country_allowed(self, e164: str) -> bool:
        if not self.allowed_country_codes:
            return True
        return any(e164.startswith("+" + code) for code in self.allowed_country_codes)


def get_settings() -> OutreachSettings:
    codes = tuple(
        c.strip().lstrip("+") for c in _env("OUTREACH_ALLOWED_COUNTRY_CODES", "1").split(",") if c.strip()
    )
    return OutreachSettings(
        twilio_account_sid=_env("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_env("TWILIO_AUTH_TOKEN"),
        twilio_from_number=_env("TWILIO_FROM_NUMBER"),
        twilio_messaging_service_sid=_env("TWILIO_MESSAGING_SERVICE_SID"),
        elevenlabs_api_key=_env("ELEVENLABS_API_KEY"),
        elevenlabs_agent_id=_env("ELEVENLABS_AGENT_ID"),
        elevenlabs_phone_number_id=_env("ELEVENLABS_PHONE_NUMBER_ID"),
        elevenlabs_api_base=_env("ELEVENLABS_API_BASE", ELEVENLABS_API_BASE).rstrip("/"),
        public_app_url=_env("PUBLIC_APP_URL", DEFAULT_PUBLIC_APP_URL).rstrip("/"),
        allowed_country_codes=codes,
    )


# ---- HTTP client -----------------------------------------------------------------
# Tests swap in an httpx.MockTransport here so nothing ever reaches Twilio or ElevenLabs.

_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def http_client() -> httpx.Client:
    return httpx.Client(timeout=HTTP_TIMEOUT, transport=_transport, follow_redirects=False)
