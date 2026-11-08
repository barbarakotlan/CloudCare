import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_patient_for_clinician
from app.database import get_db
from app.models import Escalation, Patient, RiskScore, SymptomLog, User
from app.schemas import RiskOut, SymptomIn, SymptomOut, SymptomResult
from app.services.ml_service import score_risk

router = APIRouter(prefix="/symptoms", tags=["symptoms"])


def _patient_for(user: User, db: Session, patient_id: uuid.UUID | None) -> Patient:
    """Patients get themselves; clinicians must pass ?patient_id= for an assigned patient."""
    if user.role == "patient":
        patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
        if patient is None:
            raise HTTPException(404, "No patient profile for this account")
        return patient
    if patient_id is None:
        raise HTTPException(422, "patient_id is required for clinicians")
    return get_patient_for_clinician(db, user, patient_id)


@router.post("", response_model=SymptomResult, status_code=201)
def log_symptoms(body: SymptomIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Patient check-in -> risk score -> escalation if high."""
    if user.role != "patient":
        raise HTTPException(403, "Patients only")
    patient = _patient_for(user, db, None)

    log, risk, escalated = record_checkin(db, patient, body)
    db.commit()
    db.refresh(risk)
    return SymptomResult(symptom_log_id=log.id, risk=RiskOut.model_validate(risk), escalated=escalated)


def record_checkin(db: Session, patient: Patient, body: SymptomIn) -> tuple[SymptomLog, RiskScore, bool]:
    """Saves one check-in, scores it, and opens a high_risk escalation if the score is high.

    Shared by POST /symptoms and Foggy's chat check-in. Does not commit.
    Returns (symptom log, risk score, escalated).
    """
    log = SymptomLog(patient_id=patient.id, **body.model_dump())
    db.add(log)
    db.flush()  # gives log.id

    dob = patient.date_of_birth
    result = score_risk(
        symptoms=body.model_dump(),
        patient={
            "procedure_type": patient.procedure_type,
            "days_since_surgery": (date.today() - patient.surgery_date).days,
            "age": (date.today() - dob).days // 365 if dob else None,
            "comorbidities": patient.comorbidities,
        },
    )
    risk = RiskScore(patient_id=patient.id, symptom_log_id=log.id, **result)
    db.add(risk)
    db.flush()

    escalated = result["risk_level"] == "high"
    if escalated:
        factors = ", ".join(f["feature"] for f in result["top_factors"]) or "multiple symptoms"
        db.add(Escalation(
            patient_id=patient.id, trigger_type="high_risk", severity="high", risk_score_id=risk.id,
            summary=f"Risk score {result['score']:.2f} at check-in. Top factors: {factors}.",
        ))
    return log, risk, escalated


@router.get("", response_model=list[SymptomOut])
def symptom_history(
    patient_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Newest first. Patients see their own; clinicians pass ?patient_id=."""
    patient = _patient_for(user, db, patient_id)
    return db.scalars(
        select(SymptomLog).where(SymptomLog.patient_id == patient.id).order_by(SymptomLog.logged_at.desc())
    ).all()
