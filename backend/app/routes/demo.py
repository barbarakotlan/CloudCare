"""Reset the shared demo patient (patient@demo.com) to a clean starting point.

Everyone who tries the demo signs in as the same patient, so this clears that one
patient's activity for everyone: chat, Foggy's conversation state, check-ins, risk
scores, escalations, dose answers, and texts/calls history. The account, profile,
care plan, medications, appointments and MyChart connection stay as they are.
The two earlier seeded check-ins are put back so the risk history is not blank.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.demo_data import add_jordan_baseline_checkins
from app.models import (
    ChatMessage, ChatSession, Escalation, Medication, MedicationLog, OutreachLog, Patient, RiskScore, SymptomLog, User,
)
from app.outreach import log as outreach_log
from app.schemas import DemoResetOut

log = logging.getLogger("cloudcare.demo")

router = APIRouter(prefix="/demo", tags=["demo"])

DEMO_PATIENT_EMAIL = "patient@demo.com"
DEMO_EMAIL_DOMAIN = "@demo.com"


def require_reset_permission(user: User = Depends(get_current_user)) -> User:
    """Any clinician, or a patient signed in with a demo account."""
    if user.role == "clinician":
        return user
    if user.role == "patient" and (user.email or "").strip().lower().endswith(DEMO_EMAIL_DOMAIN):
        return user
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clinicians or demo accounts can reset the demo patient")


@router.post("/reset", response_model=DemoResetOut)
def reset_demo_patient(db: Session = Depends(get_db), user: User = Depends(require_reset_permission)):
    patient = db.scalar(
        select(Patient).join(User, Patient.user_id == User.id).where(User.email == DEMO_PATIENT_EMAIL)
    )
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo patient not found")
    pid = patient.id

    med_ids = select(Medication.id).where(Medication.patient_id == pid)
    # Escalations first: they point at chat messages and risk scores; risk scores point at check-ins.
    statements = [
        ("escalations", delete(Escalation).where(Escalation.patient_id == pid)),
        ("risk_scores", delete(RiskScore).where(RiskScore.patient_id == pid)),
        ("symptom_logs", delete(SymptomLog).where(SymptomLog.patient_id == pid)),
        ("chat_messages", delete(ChatMessage).where(ChatMessage.patient_id == pid)),
        ("chat_sessions", delete(ChatSession).where(ChatSession.patient_id == pid)),
        ("medication_logs", delete(MedicationLog).where(MedicationLog.medication_id.in_(med_ids))),
        ("outreach_log", delete(OutreachLog).where(OutreachLog.patient_id == pid)),
    ]
    counts: dict[str, int] = {}
    try:
        for name, stmt in statements:
            counts[name] = db.execute(stmt.execution_options(synchronize_session=False)).rowcount or 0
        db.flush()
        restored_count = add_jordan_baseline_checkins(db, patient)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("demo.reset.failed")
        raise
    db.expire_all()

    # Texts/calls rate limits held in memory for this patient.
    for channel in ("sms", "call"):
        outreach_log.release(pid, channel)

    restored = {"symptom_logs": restored_count, "risk_scores": restored_count}
    log.info("demo.reset by_role=%s deleted=%s", user.role, sum(counts.values()))
    return DemoResetOut(reset=True, counts=counts, restored=restored)
