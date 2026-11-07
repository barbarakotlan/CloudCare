"""Extra demo patients so the clinician dashboard has a realistic queue.

Each patient tells one part of the story:
  Robert Miller   cardiac, told Foggy he's short of breath      -> emergency escalation (open)
  Maria Gonzalez  abdominal, check-ins getting worse            -> high-risk escalation (open)
  Wei Chen        hip, asked something not in the care plan     -> unanswered question (open), medium risk
  Aisha Brown     shoulder, recovering well                     -> old escalation resolved with notes

Risk scores are computed by the real model (services/ml_service.score_risk), not hard-coded.
Created once per patient (matched by email); safe to run on every startup.
All accounts use the demo password, but they are local-only (not created in Supabase Auth).
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import CarePlan, CarePlanChunk, ChatMessage, Escalation, Patient, RiskScore, SymptomLog, User
from app.routes.patients import split_into_chunks
from app.services.ml_service import score_risk

DEMO_PASSWORD = "demo123"


def _at(days_ago: float, hour: int = 9, minute: int = 0) -> datetime:
    """A UTC timestamp `days_ago` days back, at a given hour (UTC)."""
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


CARE_PLANS = {
    "abdominal": ("Laparoscopic Appendectomy: Home Recovery", """Wound care:
Keep the small incisions clean and dry. You may shower after 24 hours. Pat the incisions dry. Do not take a bath or swim for 2 weeks.

Activity:
Walk several times a day. Do not lift anything heavier than 10 pounds for 2 weeks. You may return to desk work after 1 week.

Diet:
Start with clear liquids, then light meals. Eat more fiber and drink plenty of water to avoid constipation.

Medications:
Take Ibuprofen 400 mg every 6 hours as needed for pain, with food. Take Acetaminophen 650 mg every 6 hours if pain is not controlled.

When to call:
Call your surgeon for fever over 101 F, redness, swelling or pus at an incision, vomiting that will not stop, or belly pain that keeps getting worse."""),
    "hip": ("Total Hip Replacement: Home Recovery", """Hip precautions:
Do not bend your hip past 90 degrees. Do not cross your legs. Do not turn your operated leg inward. Use a raised toilet seat.

Wound care:
Keep the dressing dry. You may shower after 5 days if the incision is dry. Do not soak in a tub for 4 weeks.

Activity:
Walk with your walker 4 to 5 times a day. Do your physical therapy exercises 3 times a day. No driving for 6 weeks.

Medications:
Take Enoxaparin 40 mg injection once daily for 4 weeks to prevent blood clots. Take Acetaminophen 1000 mg every 8 hours.

When to call:
Call your surgeon for fever over 101.5 F, increasing hip pain, a leg that looks shorter or turned, or calf pain and swelling. Call 911 for chest pain or trouble breathing."""),
    "cardiac": ("Coronary Bypass (CABG): Home Recovery", """Sternal precautions:
Do not lift more than 5 pounds for 6 weeks. Do not push or pull with your arms. Hug a pillow when you cough or sneeze.

Wound care:
Shower daily with mild soap and let water run over the incisions. Do not use lotions or powders on the incisions.

Activity:
Walk 3 to 4 times a day and slowly increase the distance. No driving for 4 to 6 weeks. Attend cardiac rehab when scheduled.

Weight and swelling:
Weigh yourself every morning. Call if you gain more than 3 pounds in one day or 5 pounds in one week.

When to call:
Call 911 for chest pain, shortness of breath, or fainting. Call your surgeon for fever over 101 F or redness or drainage from an incision."""),
    "shoulder": ("Rotator Cuff Repair: Home Recovery", """Sling:
Wear your sling at all times for 4 weeks, including while sleeping. Remove it only to shower and do your exercises.

Wound care:
Keep the dressing dry for 3 days. After that you may shower. Do not soak the shoulder for 3 weeks.

Activity:
Do your pendulum exercises 3 times a day. Do not lift, push or pull with the operated arm. No driving while in the sling.

Pain and swelling:
Use the ice machine or ice packs 20 minutes at a time. Sleeping in a recliner may be more comfortable.

When to call:
Call your surgeon for fever over 101 F, increasing redness or drainage, or numbness in the hand that does not go away."""),
}

# Symptom check-ins: (days_ago, hour_utc, symptoms). Oldest first.
PATIENTS = [
    {
        "email": "robert@demo.com", "full_name": "Robert Miller",
        "procedure_name": "Coronary artery bypass graft (CABG x3)", "procedure_type": "cardiac", "plan": "cardiac",
        "surgery_days_ago": 6, "dob": date(1955, 2, 3), "comorbidities": ["diabetes", "smoker"],
        "checkins": [
            (2, 14, dict(pain_level=4, temperature_f=98.9, mobility_level=2)),
            (1, 14, dict(pain_level=5, temperature_f=99.4, swelling=True, mobility_level=2)),
        ],
        "chat": [
            (0.02, "patient", "I've had shortness of breath since this morning, even sitting down."),
            (0.02, "assistant", "What you're describing can be an emergency. Please call 911 now. I've also alerted your care team."),
        ],
        "escalations": [
            dict(trigger_type="red_flag", severity="emergency", status="open", chat_index=0, days_ago=0.02,
                 summary='Possible emergency. Patient said: "I\'ve had shortness of breath since this morning, even sitting down."'),
        ],
    },
    {
        "email": "maria@demo.com", "full_name": "Maria Gonzalez",
        "procedure_name": "Laparoscopic appendectomy", "procedure_type": "abdominal", "plan": "abdominal",
        "surgery_days_ago": 5, "dob": date(1988, 9, 21), "comorbidities": [],
        "checkins": [
            (2, 13, dict(pain_level=3, temperature_f=98.7, mobility_level=3)),
            (1, 13, dict(pain_level=5, temperature_f=99.9, wound_redness=True, mobility_level=3)),
            (0.1, 13, dict(pain_level=7, temperature_f=101.8, wound_redness=True, wound_drainage=True,
                           nausea=True, mobility_level=2, free_text="Incision is warm and leaking a little.")),
        ],
        "chat": [
            (1, "patient", "Is it normal for the incision to be a bit red?"),
            (1, "assistant", "Your care plan says to call your surgeon if there is redness, swelling or pus at an incision. Please keep an eye on it and call if it gets worse."),
        ],
        "escalations": [],  # the high-risk escalation is created from her latest check-in
    },
    {
        "email": "wei@demo.com", "full_name": "Wei Chen",
        "procedure_name": "Total hip replacement (left)", "procedure_type": "orthopedic", "plan": "hip",
        "surgery_days_ago": 9, "dob": date(1949, 12, 8), "comorbidities": ["obesity"],
        "checkins": [
            (3, 15, dict(pain_level=5, temperature_f=98.8, mobility_level=2)),
            (1, 15, dict(pain_level=6, temperature_f=99.6, swelling=True, nausea=True, mobility_level=1)),
        ],
        "chat": [
            (0.3, "patient", "Can I sleep on my side yet?"),
            (0.3, "assistant", "I don't see that in your care plan, so I don't want to guess. I've sent your question to your care team, and they'll get back to you."),
        ],
        "escalations": [
            dict(trigger_type="unanswered_question", severity="low", status="open", chat_index=0, days_ago=0.3,
                 summary='Not covered by care plan. Patient asked: "Can I sleep on my side yet?"'),
        ],
    },
    {
        "email": "aisha@demo.com", "full_name": "Aisha Brown",
        "procedure_name": "Arthroscopic rotator cuff repair (right)", "procedure_type": "general", "plan": "shoulder",
        "surgery_days_ago": 14, "dob": date(1979, 4, 30), "comorbidities": [],
        "checkins": [
            (7, 16, dict(pain_level=6, temperature_f=99.1, swelling=True, mobility_level=3)),
            (3, 16, dict(pain_level=3, temperature_f=98.5, mobility_level=4)),
            (0.2, 16, dict(pain_level=2, temperature_f=98.4, mobility_level=4)),
        ],
        "chat": [
            (6, "patient", "Can I take the sling off to sleep?"),
            (6, "assistant", "Your care plan says to wear your sling at all times for 4 weeks, including while sleeping."),
            (5, "patient", "My fingers felt tingly last night."),
            (5, "assistant", "I don't see that in your care plan, so I don't want to guess. I've sent your question to your care team, and they'll get back to you."),
        ],
        "escalations": [
            dict(trigger_type="unanswered_question", severity="low", status="resolved", chat_index=2, days_ago=5,
                 summary='Not covered by care plan. Patient said: "My fingers felt tingly last night."',
                 clinician_notes="Called patient. Sling strap was too tight; adjusted. Tingling resolved.",
                 resolved_days_ago=4.8),
        ],
    },
]

# Earlier check-ins for the main demo patient (Jordan). Both low, so a live fever check-in stands out.
JORDAN_CHECKINS = [
    (2, 14, dict(pain_level=5, temperature_f=98.9, swelling=True, mobility_level=2)),
    (1, 14, dict(pain_level=4, temperature_f=98.6, swelling=True, mobility_level=3)),
]


def _add_checkins(db: Session, patient: Patient, checkins: list, escalate_high: bool) -> None:
    for days_ago, hour, symptoms in checkins:
        logged_at = _at(days_ago, hour)
        full = {"wound_redness": False, "wound_drainage": False, "swelling": False, "nausea": False,
                "shortness_of_breath": False, **symptoms}
        log = SymptomLog(patient_id=patient.id, logged_at=logged_at, source="checkin", **full)
        db.add(log)
        db.flush()

        dob = patient.date_of_birth
        result = score_risk(full, {
            "procedure_type": patient.procedure_type,
            "days_since_surgery": (logged_at.date() - patient.surgery_date).days,
            "age": (logged_at.date() - dob).days // 365 if dob else None,
            "comorbidities": patient.comorbidities,
        })
        risk = RiskScore(patient_id=patient.id, symptom_log_id=log.id, created_at=logged_at, **result)
        db.add(risk)
        db.flush()

        if escalate_high and result["risk_level"] == "high":
            factors = ", ".join(f["feature"] for f in result["top_factors"]) or "multiple symptoms"
            db.add(Escalation(
                patient_id=patient.id, trigger_type="high_risk", severity="high", status="open",
                risk_score_id=risk.id, created_at=logged_at,
                summary=f"Risk score {result['score']:.2f} at check-in. Top factors: {factors}.",
            ))


def seed_demo_cohort(db: Session, clinician: User, jordan: Patient) -> None:
    for spec in PATIENTS:
        if db.scalar(select(User).where(User.email == spec["email"])) is not None:
            continue  # already created on an earlier startup

        user = User(email=spec["email"], full_name=spec["full_name"], role="patient",
                    password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()

        patient = Patient(
            user_id=user.id, clinician_id=clinician.id,
            procedure_name=spec["procedure_name"], procedure_type=spec["procedure_type"],
            surgery_date=date.today() - timedelta(days=spec["surgery_days_ago"]),
            discharge_date=date.today() - timedelta(days=max(spec["surgery_days_ago"] - 2, 0)),
            date_of_birth=spec["dob"], comorbidities=spec["comorbidities"],
        )
        db.add(patient)
        db.flush()

        title, text = CARE_PLANS[spec["plan"]]
        plan = CarePlan(patient_id=patient.id, created_by=clinician.id, title=title, raw_text=text,
                        created_at=_at(spec["surgery_days_ago"], 18))
        for i, (section, content) in enumerate(split_into_chunks(text)):
            plan.chunks.append(CarePlanChunk(patient_id=patient.id, chunk_index=i, section=section, content=content))
        db.add(plan)

        _add_checkins(db, patient, spec["checkins"], escalate_high=True)

        messages = []
        for days_ago, role, content in spec["chat"]:
            m = ChatMessage(
                patient_id=patient.id, role=role, content=content, created_at=_at(days_ago, 12),
                red_flag=role == "assistant" and "911" in content,
                answered_from_plan=None if role == "patient" else ("care plan says" in content),
            )
            db.add(m)
            messages.append(m)
        db.flush()

        for e in spec["escalations"]:
            db.add(Escalation(
                patient_id=patient.id, trigger_type=e["trigger_type"], severity=e["severity"], status=e["status"],
                summary=e["summary"], chat_message_id=messages[e["chat_index"]].id, created_at=_at(e["days_ago"], 12),
                clinician_notes=e.get("clinician_notes"),
                reviewed_by=clinician.id if e["status"] != "open" else None,
                resolved_at=_at(e["resolved_days_ago"], 15) if "resolved_days_ago" in e else None,
            ))

    # Jordan: add earlier check-ins once (only if he has none yet).
    has_checkins = db.scalar(select(SymptomLog.id).where(SymptomLog.patient_id == jordan.id).limit(1))
    if has_checkins is None:
        _add_checkins(db, jordan, JORDAN_CHECKINS, escalate_high=False)
