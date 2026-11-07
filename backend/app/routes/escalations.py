import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.auth import require_clinician
from app.database import get_db
from app.models import Escalation, Patient, User
from app.schemas import EscalationOut, EscalationUpdate

router = APIRouter(prefix="/escalations", tags=["escalations"])

SEVERITY_ORDER = case(
    {"emergency": 0, "high": 1, "medium": 2, "low": 3}, value=Escalation.severity, else_=4
)


def to_out(e: Escalation) -> EscalationOut:
    return EscalationOut(
        id=e.id, patient_id=e.patient_id, patient_name=e.patient.user.full_name,
        trigger_type=e.trigger_type, severity=e.severity, summary=e.summary, status=e.status,
        clinician_notes=e.clinician_notes, created_at=e.created_at, resolved_at=e.resolved_at,
    )


@router.get("", response_model=list[EscalationOut])
def list_escalations(
    status: Literal["open", "acknowledged", "resolved", "active", "all"] = "active",
    db: Session = Depends(get_db),
    clinician: User = Depends(require_clinician),
):
    """Care-team queue for this clinician's patients. Most urgent first.

    status: 'active' (default) = open + acknowledged, or one specific status, or 'all'.
    """
    q = select(Escalation).join(Patient).where(Patient.clinician_id == clinician.id)
    if status == "active":
        q = q.where(Escalation.status != "resolved")
    elif status != "all":
        q = q.where(Escalation.status == status)
    q = q.order_by(SEVERITY_ORDER, Escalation.created_at.desc())
    return [to_out(e) for e in db.scalars(q)]


@router.patch("/{escalation_id}", response_model=EscalationOut)
def update_escalation(
    escalation_id: uuid.UUID,
    body: EscalationUpdate,
    db: Session = Depends(get_db),
    clinician: User = Depends(require_clinician),
):
    """Clinician acknowledges or resolves an escalation and can leave notes."""
    e = db.get(Escalation, escalation_id)
    if e is None or e.patient.clinician_id != clinician.id:
        raise HTTPException(404, "Escalation not found")
    e.status = body.status
    if body.clinician_notes is not None:
        e.clinician_notes = body.clinician_notes
    e.reviewed_by = clinician.id
    e.resolved_at = datetime.now(timezone.utc) if body.status == "resolved" else None
    db.commit()
    db.refresh(e)
    return to_out(e)
