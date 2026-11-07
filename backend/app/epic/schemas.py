"""Request/response shapes for /epic/*. Mirrored in frontend/src/lib/api/epic.ts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConnectStartOut(BaseModel):
    authorize_url: str


class ConnectCallbackIn(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=128)
    # Only present if Epic adds it to the redirect; checked against the configured base.
    iss: str | None = Field(default=None, max_length=512)


class ConnectCallbackOut(BaseModel):
    ok: bool
    patient_fhir_id: str


class EpicStatusOut(BaseModel):
    connected: bool
    patient_fhir_id: str | None = None
    issuer: str | None = None
    connected_at: datetime | None = None
    scopes: list[str] = []
    last_sync_at: datetime | None = None
    revoked: bool = False
    sandbox: bool = False


class MedicationOut(BaseModel):
    name: str
    dose_text: str | None = None
    frequency_text: str | None = None
    status: str | None = None
    authored_on: str | None = None
    prescriber: str | None = None


class LabOut(BaseModel):
    name: str
    value: str | None = None
    unit: str | None = None
    reference_range: str | None = None
    status: str | None = None
    effective_at: str | None = None
    interpretation: str | None = None


class EncounterOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str | None = None
    class_: str | None = Field(default=None, alias="class")
    start: str | None = None
    end: str | None = None
    location: str | None = None
    reason: str | None = None


class NoteOut(BaseModel):
    title: str
    type: str | None = None
    date: str | None = None
    author: str | None = None
    status: str | None = None
    content_preview: str | None = None
    # True when content_preview is the whole note (short text notes).
    has_full_text: bool = False


class EpicRecordsOut(BaseModel):
    medications: list[MedicationOut]
    labs: list[LabOut]
    encounters: list[EncounterOut]
    notes: list[NoteOut]
    # Resources Epic didn't return (not granted, not available, or errored).
    missing: list[str]
    missing_reasons: dict[str, str]
    fetched_at: datetime
