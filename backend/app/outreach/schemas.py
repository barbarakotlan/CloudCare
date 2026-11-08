from typing import Literal

from pydantic import BaseModel


class CapabilityLimits(BaseModel):
    sms_seconds: int
    call_seconds: int


class CapabilitiesOut(BaseModel):
    sms: bool
    call: bool
    # Plain-language reason per channel when it can't be used ("sms", "call").
    reasons: dict[str, str]
    phone_on_file: bool
    phone_last4: str | None
    limits: CapabilityLimits


class SmsIn(BaseModel):
    kind: Literal["checkin", "plan_summary"] = "checkin"


class SmsOut(BaseModel):
    # sent = Twilio accepted the text for delivery. It does not mean it was read.
    status: Literal["sent", "failed"]
    provider_id: str | None = None
    to_last4: str
    detail: str | None = None


class SmsStatusOut(BaseModel):
    provider_id: str
    # Twilio's own status: queued, sending, sent, delivered, undelivered, failed, ...
    delivery: str
    failed: bool
    detail: str | None = None


class CallIn(BaseModel):
    kind: Literal["checkin"] = "checkin"


class CallOut(BaseModel):
    # started = the phone call is being dialed. It does not mean anyone answered.
    status: Literal["started", "failed"]
    conversation_id: str | None = None
    to_last4: str
    detail: str | None = None
