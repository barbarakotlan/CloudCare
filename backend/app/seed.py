"""Creates demo accounts + a demo patient with a care plan if they don't exist. Runs on app startup.

When SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, the two demo accounts are
also created in Supabase Auth (same emails, password demo123) and the local `users`
rows reuse the Supabase user ids, so either sign-in method lands on the same data.
"""

import logging
import os
import uuid
from datetime import date, datetime, time, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SUPABASE_URL, hash_password
from app.demo_data import seed_demo_cohort
from app.models import Appointment, CarePlan, CarePlanChunk, Medication, Patient, User
from app.routes.patients import split_into_chunks

log = logging.getLogger("cloudcare.seed")

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


# ---- Supabase Auth (Admin API) ---------------------------------------------------

def _supabase_admin_key() -> str:
    # Server-only key. Either the legacy service_role JWT or a new sb_secret_ key.
    return (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY") or "").strip()


def _admin_headers(key: str) -> dict:
    headers = {"apikey": key, "Content-Type": "application/json"}
    # Legacy service_role keys are JWTs and also go in Authorization. New sb_secret_
    # keys are not JWTs and must only be sent in the apikey header.
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _find_auth_user(client: httpx.Client, email: str) -> dict | None:
    for page in range(1, 21):
        res = client.get("/admin/users", params={"page": page, "per_page": 100})
        res.raise_for_status()
        users = res.json().get("users") or []
        for user in users:
            if (user.get("email") or "").lower() == email:
                return user
        if len(users) < 100:
            return None
    return None


def _ensure_auth_user(client: httpx.Client, email: str, full_name: str, role: str) -> str | None:
    """Creates (or finds) one Supabase Auth user. Returns its id, or None on failure."""
    res = client.post(
        "/admin/users",
        json={
            "email": email,
            "password": DEMO_PASSWORD,
            "email_confirm": True,
            # Role lives in app_metadata: only the service role can change it.
            "app_metadata": {"role": role},
            "user_metadata": {"full_name": full_name},
        },
    )
    if res.status_code in (200, 201):
        log.info("Created Supabase Auth user %s.", email)
        return res.json()["id"]
    if res.status_code in (401, 403):
        log.error(
            "Supabase Admin API rejected the key (HTTP %s). Check SUPABASE_SERVICE_ROLE_KEY.", res.status_code
        )
        return None
    if res.status_code != 422:
        log.error("Could not create Supabase Auth user %s: HTTP %s %s", email, res.status_code, res.text[:300])
        return None

    # 422 = already registered (error_code email_exists). Look it up instead.
    existing = _find_auth_user(client, email)
    if existing is None:
        log.error("Supabase refused to create %s (HTTP 422: %s) and it was not found.", email, res.text[:300])
        return None
    if (existing.get("app_metadata") or {}).get("role") != role:
        update = client.put(f"/admin/users/{existing['id']}", json={"app_metadata": {"role": role}})
        if update.is_success:
            log.info("Set app_metadata.role=%s on Supabase user %s.", role, email)
        else:
            log.warning("Could not set the role on Supabase user %s: HTTP %s", email, update.status_code)
    return existing["id"]


def ensure_supabase_demo_users(db: Session) -> dict[str, uuid.UUID]:
    """Makes sure the demo accounts exist in Supabase Auth.

    Returns {email: supabase_user_id} for the accounts it could confirm. Does nothing
    (returns {}) unless SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are both set, and
    never raises: a Supabase problem is logged and the API still starts.
    """
    key = _supabase_admin_key()
    if not SUPABASE_URL or not key:
        if SUPABASE_URL:
            log.info("SUPABASE_SERVICE_ROLE_KEY not set; skipping Supabase demo users.")
        return {}

    ids: dict[str, uuid.UUID] = {}
    try:
        with httpx.Client(
            base_url=f"{SUPABASE_URL}/auth/v1", headers=_admin_headers(key), timeout=httpx.Timeout(10.0)
        ) as client:
            for demo in DEMO_USERS:
                user_id = _ensure_auth_user(client, demo["email"], demo["full_name"], demo["role"])
                if user_id:
                    ids[demo["email"]] = uuid.UUID(user_id)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.error("Supabase demo user setup failed (%s: %s); continuing without it.", type(exc).__name__, exc)

    # Local rows that predate Supabase keep their ids: changing a primary key would
    # break the foreign keys that point at it. Sign-in still works via the email match.
    for email, supabase_id in ids.items():
        local = db.scalar(select(User).where(User.email == email))
        if local is not None and local.id != supabase_id:
            log.warning(
                "Local user %s has id %s but the Supabase user id is %s; leaving the local id as is.",
                email, local.id, supabase_id,
            )
    return ids


# ---- Local demo data ------------------------------------------------------------

def _get_or_create_user(
    db: Session, email: str, full_name: str, role: str, user_id: uuid.UUID | None = None
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=full_name, role=role, password_hash=hash_password(DEMO_PASSWORD))
        if user_id is not None:
            user.id = user_id
        db.add(user)
        db.flush()
    return user


def seed_demo_users(db: Session) -> None:
    supabase_ids = ensure_supabase_demo_users(db)
    users = {u["role"]: _get_or_create_user(db, **u, user_id=supabase_ids.get(u["email"])) for u in DEMO_USERS}
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

    _seed_reminders(db, patient)
    seed_demo_cohort(db, clinician, patient)
    db.commit()


def _seed_reminders(db: Session, patient: Patient) -> None:
    """Medications and appointments matching the demo care plan.

    Checked separately from the patient so databases created before reminders existed get them too.
    """
    has_meds = db.scalar(select(Medication.id).where(Medication.patient_id == patient.id).limit(1))
    if has_meds is None:
        start = patient.surgery_date
        db.add_all([
            Medication(patient_id=patient.id, name="Acetaminophen", dosage="1000 mg",
                       instructions="Every 8 hours.", times_of_day=["06:00", "14:00", "22:00"], start_date=start),
            Medication(patient_id=patient.id, name="Aspirin", dosage="81 mg",
                       instructions="Twice daily for 4 weeks to prevent blood clots.",
                       times_of_day=["08:00", "20:00"], start_date=start, end_date=start + timedelta(weeks=4)),
            Medication(patient_id=patient.id, name="Oxycodone", dosage="5 mg",
                       instructions="Only as needed for severe pain. No driving while taking it.",
                       times_of_day=[], start_date=start),
        ])

    has_appts = db.scalar(select(Appointment.id).where(Appointment.patient_id == patient.id).limit(1))
    if has_appts is None:
        # Times in UTC: 15:30 / 14:00 UTC is 10:30 / 9:00 AM US Eastern.
        tomorrow = date.today() + timedelta(days=1)
        follow_up = patient.surgery_date + timedelta(days=14)
        db.add_all([
            Appointment(patient_id=patient.id, title="Physical therapy", provider_name="Sam Rivera, PT",
                        location="Outpatient Rehab, Building B",
                        scheduled_at=datetime.combine(tomorrow, time(15, 30), tzinfo=timezone.utc),
                        notes="Bring your walker and wear loose shorts."),
            Appointment(patient_id=patient.id, title="Post-op follow-up", provider_name="Dr. Priya Patel",
                        location="Orthopedic Clinic, 3rd floor",
                        scheduled_at=datetime.combine(follow_up, time(14, 0), tzinfo=timezone.utc),
                        notes="Incision check and staple removal."),
        ])
