"""Request and response shapes for /sales (public sales chat and onboarding requests)."""

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CHAT_HISTORY_IN = 40     # accepted; the prompt only uses the last 12
MAX_TRANSCRIPT_IN = 200      # accepted; only the last 40 are stored
TRANSCRIPT_KEEP = 40
TURN_MAX_CHARS = 4000

_EMAIL = re.compile(r"^[^@\s<>()\[\],;:\"]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")
_PHONE = re.compile(r"^[0-9+()\-.\s xX#ext]{7,40}$")


class Turn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=TURN_MAX_CHARS)


class SalesChatIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_CHAT_HISTORY_IN)
    page: str | None = Field(default=None, max_length=300)

    @field_validator("session_id")
    @classmethod
    def _uuid(cls, value: str) -> str:
        try:
            return str(uuid.UUID(value.strip()))
        except ValueError:
            raise ValueError("session_id must be a UUID") from None

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message is empty")
        return value


class SalesChatOut(BaseModel):
    reply: str
    suggestions: list[str]
    cta: Literal["onboard"] | None
    provider: Literal["gemini", "rules"]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class SalesLeadIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1, max_length=64)
    hospital: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    work_email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    discharges_per_month: str | None = Field(default=None, max_length=60)
    ehr: str | None = Field(default=None, max_length=100)
    service_lines: str | None = Field(default=None, max_length=300)
    timeline: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    transcript: list[Turn] | None = Field(default=None, max_length=MAX_TRANSCRIPT_IN)
    page: str | None = Field(default=None, max_length=300)
    # Honeypot: a hidden field people never fill in. Non-empty -> 200, nothing stored.
    website: str | None = Field(default=None, max_length=500)

    @field_validator("session_id", "hospital", "contact_name", "role")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("this field is required")
        return value

    @field_validator("phone", "discharges_per_month", "ehr", "service_lines", "timeline", "notes", "page", "website")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("work_email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip()
        if not _EMAIL.match(value):
            raise ValueError("enter a valid work email")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is not None and not _PHONE.match(value):
            raise ValueError("enter a valid phone number")
        return value


class RenderedEmailOut(BaseModel):
    to: str
    subject: str
    body: str
    # 'stored' when sending is off; 'sent' or 'failed' when the API tried to send it.
    delivery: Literal["sent", "stored", "failed"] = "stored"


class SalesLeadCreated(BaseModel):
    id: uuid.UUID
    status: Literal["stored"]
    email: RenderedEmailOut


class SalesLeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    hospital: str
    contact_name: str
    role: str
    work_email: str
    phone: str | None
    discharges_per_month: str | None
    ehr: str | None
    service_lines: str | None
    timeline: str | None
    notes: str | None
    email_subject: str | None = None
