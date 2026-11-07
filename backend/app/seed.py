"""Creates demo accounts + a demo patient with a care plan if they don't exist. Runs on app startup."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import CarePlan, CarePlanChunk, Patient, User
from app.routes.patients import split_into_chunks

DEMO_PASSWORD = "demo123"
DEMO_USERS = [
    {"email": "patient@demo.com", "full_name": "Jordan Lee", "role": "patient"},
    {"email": "clinician@demo.com", "full_name": "Dr. Priya Patel", "role": "clinician"},
]

DEMO_CARE_PLAN = """Wound care:
Keep the incision clean and dry. You may shower 48 hours after surgery with the waterproof dressing on. Do not soak in a bath, pool or hot tub for 4 weeks. Change the dressing every 2 days.

Activity:
Walk with your walker at least 3 times a day. Do your physical therapy exercises twice daily. No driving for 4 weeks or while taking opioid pain medicine.

Pain and swelling:
Ice the knee 20 minutes at a time, several times a day. Keep your leg elevated above heart level when resting. Some swelling and bruising is normal for 2 to 3 weeks.

Medications:
Take Acetaminophen 1000 mg every 8 hours. Take Oxycodone 5 mg only as needed for severe pain. Take Aspirin 81 mg twice daily for 4 weeks to prevent blood clots.

When to call:
Call your surgeon if you have a fever over 101.5 F, increasing redness or drainage from the incision, calf pain or swelling, or pain not controlled by medication. Call 911 for chest pain or trouble breathing."""


def _get_or_create_user(db: Session, email: str, full_name: str, role: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=full_name, role=role, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
    return user


def seed_demo_users(db: Session) -> None:
    users = {u["role"]: _get_or_create_user(db, **u) for u in DEMO_USERS}
    patient_user, clinician = users["patient"], users["clinician"]

    patient = db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
    if patient is None:
        patient = Patient(
            user_id=patient_user.id,
            clinician_id=clinician.id,
            procedure_name="Total knee replacement (right)",
            procedure_type="orthopedic",
            surgery_date=date.today() - timedelta(days=3),
            discharge_date=date.today() - timedelta(days=1),
            date_of_birth=date(1962, 5, 14),
            comorbidities=["diabetes"],
        )
        db.add(patient)
        db.flush()

        plan = CarePlan(
            patient_id=patient.id, created_by=clinician.id,
            title="Total Knee Replacement: Home Recovery", raw_text=DEMO_CARE_PLAN,
        )
        for i, (section, content) in enumerate(split_into_chunks(DEMO_CARE_PLAN)):
            plan.chunks.append(CarePlanChunk(patient_id=patient.id, chunk_index=i, section=section, content=content))
        db.add(plan)

    db.commit()
