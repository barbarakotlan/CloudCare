"""Extra demo patients so the clinician dashboard has a realistic, anesthesia-focused queue.

Each patient tells one part of the story:
  Robert Miller    CABG, general anesthesia; told Foggy he's short of breath     -> emergency (open)
  Maria Gonzalez   appendectomy, general; check-ins getting worse (infection)  -> high risk (open)
  Linda Park       gallbladder, general; post-op nausea & vomiting (PONV)      -> urgent (open)
  James Walker     knee scope, spinal; post-dural puncture headache            -> urgent (open)
  Harold Thompson  hip fracture, 81, general; family reports night confusion   -> possible delirium (acknowledged)
  Wei Chen         hip replacement, spinal; asked something not in the plan    -> unanswered question (open)
  Aisha Brown      shoulder, general + nerve block; rebound pain, then well    -> resolved with notes

Risk scores are computed by the real model (services/ml_service.score_risk), not hard-coded.
Several anesthesia complications (PONV, spinal headache, delirium) are caught by the patient's own
words in chat or check-in notes rather than by the ML score: two independent safety nets.

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

URGENT_REPLY = ("That could need prompt medical attention. Please call your care team now, or 911 if it feels "
                "severe. I've also alerted your care team.")
EMERGENCY_REPLY = "What you're describing can be an emergency. Please call 911 now. I've also alerted your care team."
NOT_IN_PLAN_REPLY = ("I don't see that in your care plan, so I don't want to guess. I've sent your question to "
                     "your care team, and they'll get back to you.")


def _at(days_ago: float, hour: int = 9, minute: int = 0) -> datetime:
    """A UTC timestamp `days_ago` days back, at a given hour (UTC)."""
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


# ---- "After anesthesia" sections, by anesthesia type ---------------------------------

ANESTHESIA_GENERAL = """After anesthesia:
You had general anesthesia with a breathing tube. A sore throat or hoarse voice is normal for 2 to 3 days; sip cool drinks and use throat lozenges. You may feel drowsy, foggy or forgetful for 24 hours: have an adult stay with you, and do not drive, drink alcohol, sign documents or make important decisions for 24 hours. Nausea is common on the first day: start with sips of clear fluids and eat small, bland meals. Call your care team if you cannot keep fluids down for more than 8 hours."""

ANESTHESIA_SPINAL = """After anesthesia:
You had spinal anesthesia. Your legs may feel numb or weak for several hours, so only walk with help until feeling fully returns. Do not drive, drink alcohol or make important decisions for 24 hours. A headache that gets worse when you sit or stand and better when you lie down can happen after a spinal: lie flat, drink fluids and caffeine, and call the anesthesia team if it lasts more than a few hours. Call if you cannot pass urine for 8 hours."""

ANESTHESIA_BLOCK = """After anesthesia:
You had general anesthesia and a nerve block in your neck to numb your shoulder and arm. Your arm will feel numb and heavy for 12 to 24 hours; keep it in the sling and protect it, because you cannot feel injuries. Take your pain medicine on schedule before the block wears off, usually the first evening. A droopy eyelid, hoarse voice or mild shortness of breath on the blocked side can happen and goes away as the block wears off. Call 911 if breathing becomes hard."""

ANESTHESIA_ELDERLY = """After anesthesia:
You had general anesthesia. Older adults can be confused, sleepy or agitated for a few days after surgery, especially at night. Family can help: keep glasses and hearing aids on, keep lights on during the day and a night light at night, and remind him of the date and place. Call the care team if confusion is new, gets worse, comes and goes suddenly, or if he is very hard to wake. Do not give sleeping pills unless prescribed."""

# ---- Care plans -----------------------------------------------------------------------

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
Call your surgeon for fever over 101 F, redness, swelling or pus at an incision, vomiting that will not stop, or belly pain that keeps getting worse.

""" + ANESTHESIA_GENERAL),
    "gallbladder": ("Laparoscopic Cholecystectomy: Home Recovery", """Wound care:
Keep the incisions clean and dry. You may shower after 24 hours. Do not soak in a tub for 2 weeks.

Activity:
Walk often. Shoulder pain from the gas used during surgery is common for 1 to 2 days; walking helps it pass. No heavy lifting for 2 weeks.

Diet:
Eat small, low-fat meals for the first week. Greasy food may cause cramping or loose stools.

Medications:
Take Ondansetron 4 mg every 8 hours as needed for nausea. Take Acetaminophen 1000 mg every 8 hours for pain.

When to call:
Call your surgeon for fever over 101 F, yellow skin or eyes, severe belly pain, or vomiting that will not stop.

""" + ANESTHESIA_GENERAL),
    "knee_scope": ("Knee Arthroscopy: Home Recovery", """Wound care:
Keep the dressing clean and dry for 2 days. Then you may shower and cover the small incisions with bandages.

Activity:
Use crutches as needed for 3 to 5 days. Do your quad exercises 3 times a day. You may drive when you can bend your knee and are off pain medicine.

Pain and swelling:
Ice and elevate the knee 20 minutes at a time, several times a day.

When to call:
Call your surgeon for fever over 101 F, calf pain or swelling, or redness spreading from an incision.

""" + ANESTHESIA_SPINAL),
    "hip": ("Total Hip Replacement: Home Recovery", """Hip precautions:
Do not bend your hip past 90 degrees. Do not cross your legs. Do not turn your operated leg inward. Use a raised toilet seat.

Wound care:
Keep the dressing dry. You may shower after 5 days if the incision is dry. Do not soak in a tub for 4 weeks.

Activity:
Walk with your walker 4 to 5 times a day. Do your physical therapy exercises 3 times a day. No driving for 6 weeks.

Medications:
Take Enoxaparin 40 mg injection once daily for 4 weeks to prevent blood clots. Take Acetaminophen 1000 mg every 8 hours.

When to call:
Call your surgeon for fever over 101.5 F, increasing hip pain, a leg that looks shorter or turned, or calf pain and swelling. Call 911 for chest pain or trouble breathing.

""" + ANESTHESIA_SPINAL),
    "hip_fracture": ("Hip Fracture Repair: Home Recovery", """Hip precautions:
Do not bend the hip past 90 degrees or cross the legs. Use the walker for every step. Someone should be nearby when he gets up at night.

Wound care:
Keep the dressing dry. A nurse will check the incision at the home visit on day 5.

Activity:
Walk with the walker and a helper 3 to 4 times a day. Sit up in a chair for meals.

Medications:
Take Apixaban 2.5 mg twice daily for 5 weeks to prevent blood clots. Take Acetaminophen 650 mg every 6 hours. Avoid sleeping pills and allergy medicines that cause drowsiness.

When to call:
Call the surgeon for fever over 101 F, a fall, new hip pain, or calf swelling. Call 911 for chest pain or trouble breathing.

""" + ANESTHESIA_ELDERLY),
    "cardiac": ("Coronary Bypass (CABG): Home Recovery", """Sternal precautions:
Do not lift more than 5 pounds for 6 weeks. Do not push or pull with your arms. Hug a pillow when you cough or sneeze.

Wound care:
Shower daily with mild soap and let water run over the incisions. Do not use lotions or powders on the incisions.

Activity:
Walk 3 to 4 times a day and slowly increase the distance. No driving for 4 to 6 weeks. Attend cardiac rehab when scheduled.

Weight and swelling:
Weigh yourself every morning. Call if you gain more than 3 pounds in one day or 5 pounds in one week.

When to call:
Call 911 for chest pain, shortness of breath, or fainting. Call your surgeon for fever over 101 F or redness or drainage from an incision.

""" + ANESTHESIA_GENERAL),
    "shoulder": ("Rotator Cuff Repair: Home Recovery", """Sling:
Wear your sling at all times for 4 weeks, including while sleeping. Remove it only to shower and do your exercises.

Wound care:
Keep the dressing dry for 3 days. After that you may shower. Do not soak the shoulder for 3 weeks.

Activity:
Do your pendulum exercises 3 times a day. Do not lift, push or pull with the operated arm. No driving while in the sling.

Pain and swelling:
Use the ice machine or ice packs 20 minutes at a time. Sleeping in a recliner may be more comfortable.

When to call:
Call your surgeon for fever over 101 F, increasing redness or drainage, or numbness in the hand that does not go away.

""" + ANESTHESIA_BLOCK),
}

# ---- Patients -------------------------------------------------------------------------
# checkins: (days_ago, hour_utc, symptoms), oldest first.
# chat: (days_ago, role, content[, cited section]).
# escalations: chat_index points into chat; status open | acknowledged | resolved.

PATIENTS = [
    {
        "email": "robert@demo.com", "full_name": "Robert Miller",
        "procedure_name": "Coronary artery bypass graft (CABG x3) · general anesthesia",
        "procedure_type": "cardiac", "plan": "cardiac",
        "surgery_days_ago": 6, "dob": date(1955, 2, 3), "comorbidities": ["diabetes", "smoker", "sleep apnea"],
        "checkins": [
            (2, 14, dict(pain_level=4, temperature_f=98.9, mobility_level=2)),
            (1, 14, dict(pain_level=5, temperature_f=99.4, swelling=True, mobility_level=2)),
        ],
        "chat": [
            (0.02, "patient", "I've had shortness of breath since this morning, even sitting down."),
            (0.02, "assistant", EMERGENCY_REPLY),
        ],
        "escalations": [
            dict(trigger_type="red_flag", severity="emergency", status="open", chat_index=0, days_ago=0.02,
                 summary='Possible emergency. Patient said: "I\'ve had shortness of breath since this morning, even sitting down."'),
        ],
    },
    {
        "email": "maria@demo.com", "full_name": "Maria Gonzalez",
        "procedure_name": "Laparoscopic appendectomy · general anesthesia",
        "procedure_type": "abdominal", "plan": "abdominal",
        "surgery_days_ago": 5, "dob": date(1988, 9, 21), "comorbidities": [],
        "checkins": [
            (2, 13, dict(pain_level=3, temperature_f=98.7, mobility_level=3)),
            (1, 13, dict(pain_level=5, temperature_f=99.9, wound_redness=True, mobility_level=3)),
            (0.1, 13, dict(pain_level=7, temperature_f=101.8, wound_redness=True, wound_drainage=True,
                           nausea=True, mobility_level=2, free_text="Incision is warm and leaking a little.")),
        ],
        "chat": [
            (4, "patient", "My throat is really sore and my voice is scratchy. Is that from the surgery?"),
            (4, "assistant", "Yes. A sore throat or hoarse voice is normal for 2 to 3 days after a breathing tube. "
                             "Sip cool drinks and use throat lozenges.", "After anesthesia"),
            (1, "patient", "Is it normal for the incision to be a bit red?"),
            (1, "assistant", "Your care plan says to call your surgeon if there is redness, swelling or pus at an "
                             "incision. Please keep an eye on it and call if it gets worse.", "When to call"),
        ],
        "escalations": [],  # the high-risk escalation is created from her latest check-in
    },
    {
        "email": "linda@demo.com", "full_name": "Linda Park",
        "procedure_name": "Laparoscopic cholecystectomy · general anesthesia",
        "procedure_type": "abdominal", "plan": "gallbladder",
        "surgery_days_ago": 1, "dob": date(1991, 6, 12), "comorbidities": ["history of PONV", "motion sickness"],
        "checkins": [
            (0.6, 22, dict(pain_level=4, temperature_f=98.8, nausea=True, mobility_level=2,
                           free_text="Threw up twice since getting home.")),
            (0.1, 14, dict(pain_level=5, temperature_f=99.1, nausea=True, mobility_level=1,
                           free_text="Vomited 4 times overnight. Can't keep water down. Feel dizzy standing up.")),
        ],
        "chat": [
            (0.1, "patient", "I've thrown up 4 times since last night and I can't keep any water down."),
            (0.1, "assistant", URGENT_REPLY),
        ],
        "escalations": [
            dict(trigger_type="red_flag", severity="high", status="open", chat_index=0, days_ago=0.1,
                 summary="Post-op nausea and vomiting: unable to keep fluids down for over 8 hours, dizzy on "
                         "standing. History of PONV. Possible dehydration."),
        ],
    },
    {
        "email": "james@demo.com", "full_name": "James Walker",
        "procedure_name": "Knee arthroscopy, meniscus repair (left) · spinal anesthesia",
        "procedure_type": "orthopedic", "plan": "knee_scope",
        "surgery_days_ago": 2, "dob": date(1996, 1, 27), "comorbidities": [],
        "checkins": [
            (1, 15, dict(pain_level=3, temperature_f=98.6, mobility_level=3)),
            (0.15, 15, dict(pain_level=3, temperature_f=98.7, nausea=True, mobility_level=3,
                            free_text="Bad headache at the back of my head when I sit up. Gone when I lie flat.")),
        ],
        "chat": [
            (0.15, "patient", "I have a pounding headache whenever I sit up, but it goes away when I lie down. "
                              "It's been like this all day."),
            (0.15, "assistant", URGENT_REPLY),
        ],
        "escalations": [
            dict(trigger_type="red_flag", severity="high", status="open", chat_index=0, days_ago=0.15,
                 summary="Positional headache after spinal anesthesia (worse sitting, relieved lying flat), "
                         "lasting all day. Possible post-dural puncture headache: anesthesia team to review."),
        ],
    },
    {
        "email": "harold@demo.com", "full_name": "Harold Thompson",
        "procedure_name": "Hip fracture repair, hemiarthroplasty (right) · general anesthesia",
        "procedure_type": "orthopedic", "plan": "hip_fracture",
        "surgery_days_ago": 4, "dob": date(1945, 3, 18), "comorbidities": ["hypertension", "hearing loss"],
        "checkins": [
            (2, 14, dict(pain_level=4, temperature_f=98.9, mobility_level=1)),
            (0.3, 14, dict(pain_level=4, temperature_f=99.0, mobility_level=1,
                           free_text="(Entered by daughter) Very confused last night, didn't know where he was, "
                                     "tried to get out of bed alone. Better this morning but sleepy.")),
        ],
        "chat": [
            (0.3, "patient", "This is his daughter. Dad was really confused and agitated last night and didn't "
                             "recognize the house. Is that normal?"),
            (0.3, "assistant", "Your care plan says older adults can be confused for a few days after anesthesia, "
                               "especially at night, and to call the care team if confusion is new or gets worse. "
                               "I've let your care team know.", "After anesthesia"),
        ],
        "escalations": [
            dict(trigger_type="patient_request", severity="high", status="acknowledged", chat_index=0, days_ago=0.3,
                 summary="Family reports new night-time confusion and agitation, day 4 after general anesthesia "
                         "(age 81). Possible postoperative delirium; fall risk.",
                 clinician_notes="Spoke with daughter. Reviewing medications (stopped oxycodone). "
                                 "Home nurse visit booked for tomorrow morning."),
        ],
    },
    {
        "email": "wei@demo.com", "full_name": "Wei Chen",
        "procedure_name": "Total hip replacement (left) · spinal anesthesia",
        "procedure_type": "orthopedic", "plan": "hip",
        "surgery_days_ago": 9, "dob": date(1949, 12, 8), "comorbidities": ["obesity"],
        "checkins": [
            (3, 15, dict(pain_level=5, temperature_f=98.8, mobility_level=2)),
            (1, 15, dict(pain_level=6, temperature_f=99.6, swelling=True, nausea=True, mobility_level=1)),
        ],
        "chat": [
            (0.3, "patient", "Can I sleep on my side yet?"),
            (0.3, "assistant", NOT_IN_PLAN_REPLY),
        ],
        "escalations": [
            dict(trigger_type="unanswered_question", severity="low", status="open", chat_index=0, days_ago=0.3,
                 summary='Not covered by care plan. Patient asked: "Can I sleep on my side yet?"'),
        ],
    },
    {
        "email": "aisha@demo.com", "full_name": "Aisha Brown",
        "procedure_name": "Arthroscopic rotator cuff repair (right) · general anesthesia + interscalene nerve block",
        "procedure_type": "general", "plan": "shoulder",
        "surgery_days_ago": 14, "dob": date(1979, 4, 30), "comorbidities": [],
        "checkins": [
            (13, 3, dict(pain_level=9, temperature_f=98.9, swelling=True, mobility_level=3,
                         free_text="Nerve block wore off around midnight and the pain hit all at once.")),
            (7, 16, dict(pain_level=6, temperature_f=99.1, swelling=True, mobility_level=3)),
            (3, 16, dict(pain_level=3, temperature_f=98.5, mobility_level=4)),
            (0.2, 16, dict(pain_level=2, temperature_f=98.4, mobility_level=4)),
        ],
        "chat": [
            (13.1, "patient", "My arm is still completely numb and heavy. Is that okay?"),
            (13.1, "assistant", "Yes. Your care plan says your arm will feel numb and heavy for 12 to 24 hours after "
                                "the nerve block. Keep it in the sling and take your pain medicine on schedule before "
                                "the block wears off.", "After anesthesia"),
            (6, "patient", "Can I take the sling off to sleep?"),
            (6, "assistant", "Your care plan says to wear your sling at all times for 4 weeks, including while "
                             "sleeping.", "Sling"),
            (5, "patient", "My fingers felt tingly last night."),
            (5, "assistant", NOT_IN_PLAN_REPLY),
            (4.8, "clinician", "Hi Aisha, this is Dr. Patel. Your sling strap was pressing on the nerves; loosening "
                               "it should fix the tingling. Message me if it comes back."),
        ],
        "escalations": [
            dict(trigger_type="unanswered_question", severity="low", status="resolved", chat_index=4, days_ago=5,
                 summary='Not covered by care plan. Patient said: "My fingers felt tingly last night."',
                 clinician_notes="Called patient. Sling strap was too tight; adjusted. Tingling resolved.",
                 resolved_days_ago=4.8),
        ],
    },
]

# Earlier check-ins for the main demo patient (Jordan). Both low, so a live fever check-in stands out.
JORDAN_CHECKINS = [
    (2, 14, dict(pain_level=5, temperature_f=98.9, swelling=True, mobility_level=2,
                 free_text="Nerve block wore off overnight, pain medicine helped.")),
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


def _create_patient(db: Session, spec: dict, clinician: User) -> None:
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
    db.flush()
    chunk_by_section = {c.section: c for c in plan.chunks}

    _add_checkins(db, patient, spec["checkins"], escalate_high=True)

    messages = []
    for days_ago, role, content, *cited in spec["chat"]:
        chunk = chunk_by_section.get(cited[0]) if cited else None
        m = ChatMessage(
            patient_id=patient.id, role=role, content=content, created_at=_at(days_ago, 12),
            citations=[{"chunk_id": str(chunk.id), "section": chunk.section}] if chunk else [],
            red_flag=role == "assistant" and content in (URGENT_REPLY, EMERGENCY_REPLY),
            answered_from_plan=(chunk is not None) if role == "assistant" else None,
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


def seed_demo_cohort(db: Session, clinician: User, jordan: Patient) -> None:
    for spec in PATIENTS:
        if db.scalar(select(User).where(User.email == spec["email"])) is None:
            _create_patient(db, spec, clinician)

    # Jordan: add earlier check-ins once (only if he has none yet).
    has_checkins = db.scalar(select(SymptomLog.id).where(SymptomLog.patient_id == jordan.id).limit(1))
    if has_checkins is None:
        _add_checkins(db, jordan, JORDAN_CHECKINS, escalate_high=False)
