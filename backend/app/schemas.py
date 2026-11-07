"""Request/response shapes for the API (what the frontend sends and receives)."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Patients ---------------------------------------------------------------

class RiskOut(ORM):
    score: float
    risk_level: Literal["low", "medium", "high"]
    top_factors: list[dict]
    model_version: str
    created_at: datetime


class PatientRow(BaseModel):
    """One row in the clinician's patient list."""
    id: uuid.UUID
    full_name: str
    procedure_name: str
    surgery_date: date
    latest_risk: RiskOut | None
    open_escalations: int
    last_checkin_at: datetime | None


class PatientOut(ORM):
    id: uuid.UUID
    full_name: str
    procedure_name: str
    procedure_type: str
    surgery_date: date
    discharge_date: date | None
    comorbidities: list[str]


class CarePlanIn(BaseModel):
    title: str
    raw_text: str = Field(min_length=1)


class CarePlanChunkOut(ORM):
    id: uuid.UUID
    chunk_index: int
    section: str | None
    content: str


class CarePlanOut(ORM):
    id: uuid.UUID
    title: str
    raw_text: str
    created_at: datetime
    chunks: list[CarePlanChunkOut]


# ---- Symptoms ---------------------------------------------------------------

class SymptomIn(BaseModel):
    pain_level: int = Field(ge=0, le=10)
    temperature_f: float | None = Field(default=None, ge=90, le=110)
    wound_redness: bool = False
    wound_drainage: bool = False
    swelling: bool = False
    nausea: bool = False
    shortness_of_breath: bool = False
    mobility_level: int = Field(default=4, ge=0, le=4)
    free_text: str | None = None
    source: Literal["checkin", "chat", "voice"] = "checkin"


class SymptomOut(ORM):
    id: uuid.UUID
    logged_at: datetime
    source: str
    pain_level: int | None
    temperature_f: float | None
    wound_redness: bool
    wound_drainage: bool
    swelling: bool
    nausea: bool
    shortness_of_breath: bool
    mobility_level: int | None
    free_text: str | None


class SymptomResult(BaseModel):
    symptom_log_id: uuid.UUID
    risk: RiskOut
    escalated: bool


# ---- Chat -------------------------------------------------------------------

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatMessageOut(ORM):
    id: uuid.UUID
    role: Literal["patient", "assistant", "clinician"]
    content: str
    citations: list[dict]
    answered_from_plan: bool | None
    red_flag: bool
    created_at: datetime


class ChatReply(BaseModel):
    message: ChatMessageOut
    escalated: bool


# ---- Reminders: medications & appointments ----------------------------------

class MedicationOut(ORM):
    id: uuid.UUID
    name: str
    dosage: str
    instructions: str | None
    times_of_day: list[str]  # "HH:MM", empty = as needed
    start_date: date
    end_date: date | None
    is_active: bool


class MedicationLogIn(BaseModel):
    scheduled_for: datetime  # the dose time being answered, e.g. today 08:00 local, as ISO
    status: Literal["taken", "skipped"]


class MedicationLogOut(ORM):
    id: uuid.UUID
    medication_id: uuid.UUID
    scheduled_for: datetime
    status: Literal["pending", "taken", "skipped", "missed"]
    responded_at: datetime | None


class AppointmentOut(ORM):
    id: uuid.UUID
    title: str
    provider_name: str | None
    location: str | None
    scheduled_at: datetime
    status: Literal["scheduled", "completed", "missed", "cancelled"]
    notes: str | None


# ---- Escalations ------------------------------------------------------------

class EscalationOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    trigger_type: str
    severity: str
    summary: str
    status: str
    clinician_notes: str | None
    created_at: datetime
    resolved_at: datetime | None


class EscalationUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
    clinician_notes: str | None = None
