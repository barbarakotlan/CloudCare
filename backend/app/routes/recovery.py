"""Reminders for the patient dashboard: medications, dose logs, and appointments."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_patient
from app.database import get_db
from app.models import Appointment, Medication, MedicationLog, Patient
from app.schemas import AppointmentOut, MedicationLogIn, MedicationLogOut, MedicationOut

router = APIRouter(tags=["reminders"])


def _utc(dt: datetime) -> datetime:
    """Store and compare dose times in UTC so '08:00 local' always matches the same row."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


@router.get("/patients/me/medications", response_model=list[MedicationOut])
def my_medications(db: Session = Depends(get_db), patient: Patient = Depends(get_current_patient)):
    """Active medications, alphabetical."""
    return db.scalars(
        select(Medication)
        .where(Medication.patient_id == patient.id, Medication.is_active)
        .order_by(Medication.name)
    ).all()


@router.get("/patients/me/medication-logs", response_model=list[MedicationLogOut])
def my_medication_logs(
    since: datetime | None = None,
    db: Session = Depends(get_db),
    patient: Patient = Depends(get_current_patient),
):
    """Doses already answered (taken/skipped) since `since` (ISO). Default: the last 24 hours.

    The frontend passes local midnight to get today's logs, e.g. ?since=2026-11-07T00:00:00-05:00
    """
    since_utc = _utc(since) if since else datetime.now(timezone.utc) - timedelta(hours=24)
    return db.scalars(
        select(MedicationLog)
        .join(Medication)
        .where(Medication.patient_id == patient.id, MedicationLog.scheduled_for >= since_utc)
        .order_by(MedicationLog.scheduled_for)
    ).all()


@router.post("/medications/{medication_id}/logs", response_model=MedicationLogOut)
def log_dose(
    medication_id: uuid.UUID,
    body: MedicationLogIn,
    db: Session = Depends(get_db),
    patient: Patient = Depends(get_current_patient),
):
    """Mark one scheduled dose as taken or skipped. Sending it again for the same time updates it."""
    med = db.get(Medication, medication_id)
    if med is None or med.patient_id != patient.id:
        raise HTTPException(404, "Medication not found")

    scheduled = _utc(body.scheduled_for)
    log = db.scalar(
        select(MedicationLog).where(
            MedicationLog.medication_id == med.id, MedicationLog.scheduled_for == scheduled
        )
    )
    if log is None:
        log = MedicationLog(medication_id=med.id, scheduled_for=scheduled)
        db.add(log)
    log.status = body.status
    log.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(log)
    return log


@router.get("/patients/me/appointments", response_model=list[AppointmentOut])
def my_appointments(db: Session = Depends(get_db), patient: Patient = Depends(get_current_patient)):
    """All appointments, soonest first. The frontend decides which are 'upcoming'."""
    return db.scalars(
        select(Appointment).where(Appointment.patient_id == patient.id).order_by(Appointment.scheduled_at)
    ).all()
