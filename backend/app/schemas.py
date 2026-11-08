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
    """One row in the clinician's patient list.

    Current urgency (open alerts) is kept apart from the model's risk estimate:
    open_emergencies / open_high count unresolved escalations by severity, and
    latest_risk_at says when the risk score was computed (its check-in time).
    """
    id: uuid.UUID
    full_name: str
    procedure_name: str
    surgery_date: date
    latest_risk: RiskOut | None
    open_escalations: int  # open + acknowledged, any severity
    open_emergencies: int = 0  # unresolved escalations with severity "emergency"
    open_high: int = 0  # unresolved escalations with severity "high"
    last_alert_at: datetime | None = None  # newest escalation for this patient, any status
    latest_risk_at: datetime | None = None  # same as latest_risk.created_at
    last_checkin_at: datetime | None


class UnassignedPatientOut(BaseModel):
    """A patient with no clinician yet (e.g. a self sign-up), for a clinician to claim."""
    id: uuid.UUID
    full_name: str
    procedure_name: str
    created_at: datetime


class PatientOut(ORM):
    id: uuid.UUID
    full_name: str
    procedure_name: str
    procedure_type: str
    surgery_date: date
    discharge_date: date | None
    comorbidities: list[str]
    # Mobile number in E.164 (e.g. +15551234567), or null when none is on file.
    phone: str | None = None


class PatientUpdate(BaseModel):
    """Clinician edits a patient's profile (e.g. finishing "Pending clinician setup").
    Only the fields sent are changed."""
    procedure_name: str | None = Field(default=None, min_length=1, max_length=200)
    procedure_type: str | None = Field(default=None, min_length=1, max_length=100)
    surgery_date: date | None = None
    discharge_date: date | None = None
    date_of_birth: date | None = None
    comorbidities: list[str] | None = None
    # Any common format; stored as E.164. Null or "" clears it.
    phone: str | None = Field(default=None, max_length=32)


class PatientMeUpdate(BaseModel):
    """A patient edits their own profile. Only the mobile number for now."""
    # Any common format; stored as E.164. Null or "" clears it.
    phone: str | None = Field(default=None, max_length=32)


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
    source: Literal["chat", "voice"] = "chat"  # voice = the spoken Foggy agent's tool call


FoggyRoute = Literal[
    "ANSWER_FROM_PLAN", "NOT_IN_PLAN", "REFUSE_DOSE_CHANGE", "EMERGENCY_911", "START_CHECKIN", "CALL_SURGEON",
    "OPERATIONAL",
]


class ChatMessageOut(ORM):
    id: uuid.UUID
    role: Literal["patient", "assistant", "clinician"]
    content: str
    citations: list[dict]
    answered_from_plan: bool | None
    red_flag: bool
    route: FoggyRoute | None = None  # Foggy's route for assistant messages; null for older rows
    created_at: datetime


class PendingActionOut(BaseModel):
    """An action Foggy offered and is waiting for the patient to agree to."""
    kind: Literal["message_care_team"]
    recipient: Literal["care_team"]
    reason: str


class ActionResultOut(BaseModel):
    """What actually happened this turn. "sent" = a row is in the care team's queue (not that anyone read it)."""
    kind: str
    status: Literal["sent", "failed", "simulated"]
    detail: str


class CheckinSubstep(BaseModel):
    """The medicine dose Foggy is asking about inside step 2 (one question per dose due today)."""
    medication_id: uuid.UUID
    name: str
    due_at: datetime | None  # UTC; null for an as-needed medicine ("Did you need any oxycodone today?")


class CheckinOut(BaseModel):
    step: int | Literal["done"]  # 1 pain, 2 medicines, 3 numbness/tingling/color, 4 falls
    answers: dict
    substep: CheckinSubstep | None = None  # only while step 2 is asking about a specific dose


class ChatReply(BaseModel):
    message: ChatMessageOut
    route: FoggyRoute
    offer_contact: bool = False
    pending_action: PendingActionOut | None = None
    action_result: ActionResultOut | None = None
    checkin: CheckinOut | None = None
    escalated: bool  # True only when a real escalation row was created this turn


class ChatCapabilities(BaseModel):
    message_care_team: bool
    call_care_team: bool
    emergency_call_assist: bool
    simulated: bool


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
    status: Literal["taken", "skipped", "pending"]  # pending = undo a taken/skipped answer


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
    # Who last changed the status (acknowledged, resolved or reopened), and when it was acknowledged.
    reviewed_by_name: str | None = None
    acknowledged_at: datetime | None = None


class EscalationUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
    clinician_notes: str | None = None


# ---- Demo -------------------------------------------------------------------

class DemoResetOut(BaseModel):
    """Rows removed for the shared demo patient, per table, and baseline rows put back."""
    reset: bool
    counts: dict[str, int]
    restored: dict[str, int]
