import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import get_current_patient, get_patient_for_clinician, require_clinician
from app.database import get_db
from app.models import CarePlan, CarePlanChunk, Escalation, Patient, RiskScore, SymptomLog, User
from app.schemas import CarePlanIn, CarePlanOut, PatientOut, PatientRow, RiskOut

router = APIRouter(prefix="/patients", tags=["patients"])


def to_patient_out(p: Patient) -> PatientOut:
    return PatientOut(
        id=p.id, full_name=p.user.full_name, procedure_name=p.procedure_name,
        procedure_type=p.procedure_type, surgery_date=p.surgery_date,
        discharge_date=p.discharge_date, comorbidities=p.comorbidities,
    )


@router.get("", response_model=list[PatientRow])
def list_my_patients(db: Session = Depends(get_db), clinician: User = Depends(require_clinician)):
    """Clinician dashboard: assigned patients, highest risk first."""
    rows = []
    for p in db.scalars(select(Patient).where(Patient.clinician_id == clinician.id)):
        latest = db.scalar(
            select(RiskScore).where(RiskScore.patient_id == p.id).order_by(RiskScore.created_at.desc()).limit(1)
        )
        open_count = db.scalar(
            select(func.count()).select_from(Escalation)
            .where(Escalation.patient_id == p.id, Escalation.status != "resolved")
        )
        last_checkin = db.scalar(select(func.max(SymptomLog.logged_at)).where(SymptomLog.patient_id == p.id))
        rows.append(PatientRow(
            id=p.id, full_name=p.user.full_name, procedure_name=p.procedure_name,
            surgery_date=p.surgery_date, latest_risk=RiskOut.model_validate(latest) if latest else None,
            open_escalations=open_count or 0, last_checkin_at=last_checkin,
        ))
    rows.sort(key=lambda r: (r.latest_risk.score if r.latest_risk else -1), reverse=True)
    return rows


@router.get("/me", response_model=PatientOut)
def my_profile(patient: Patient = Depends(get_current_patient)):
    return to_patient_out(patient)


@router.get("/me/care-plan", response_model=CarePlanOut | None)
def my_care_plan(db: Session = Depends(get_db), patient: Patient = Depends(get_current_patient)):
    return active_care_plan(db, patient.id)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: uuid.UUID, db: Session = Depends(get_db), clinician: User = Depends(require_clinician)):
    return to_patient_out(get_patient_for_clinician(db, clinician, patient_id))


@router.post("/{patient_id}/care-plan", response_model=CarePlanOut, status_code=201)
def upload_care_plan(
    patient_id: uuid.UUID,
    body: CarePlanIn,
    db: Session = Depends(get_db),
    clinician: User = Depends(require_clinician),
):
    """Clinician uploads new instructions. Replaces the patient's active plan."""
    patient = get_patient_for_clinician(db, clinician, patient_id)
    db.execute(update(CarePlan).where(CarePlan.patient_id == patient.id).values(is_active=False))
    plan = CarePlan(patient_id=patient.id, created_by=clinician.id, title=body.title, raw_text=body.raw_text)
    for i, (section, content) in enumerate(split_into_chunks(body.raw_text)):
        plan.chunks.append(CarePlanChunk(patient_id=patient.id, chunk_index=i, section=section, content=content))
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def active_care_plan(db: Session, patient_id: uuid.UUID) -> CarePlan | None:
    return db.scalar(select(CarePlan).where(CarePlan.patient_id == patient_id, CarePlan.is_active))


def split_into_chunks(raw_text: str) -> list[tuple[str | None, str]]:
    """Splits instructions on blank lines. A short first line ending in ':' becomes the section name.

    Example block:   "Wound care:\\nKeep the incision dry..."  ->  ("Wound care", "Keep the incision dry...")
    """
    chunks = []
    for block in (b.strip() for b in raw_text.replace("\r\n", "\n").split("\n\n")):
        if not block:
            continue
        first, _, rest = block.partition("\n")
        if first.endswith(":") and len(first) <= 60 and rest.strip():
            chunks.append((first[:-1].strip(), rest.strip()))
        else:
            chunks.append((None, block))
    return chunks
