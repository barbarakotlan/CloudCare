"""Today's scheduled medicine doses for the check-in's medication questions.

The check-in asks about each dose that was due today (in the patient's local day) before now
and has no taken/skipped answer yet, one question per dose, oldest first. As-needed medicines
(no times of day) get one question each and are recorded in the check-in text only.

Patients have no timezone yet, so the local day comes from CHECKIN_TIMEZONE (default
America/New_York). CHECKIN_NOW_OVERRIDE pins "now" for tests and local demos only: either a
full ISO datetime ("2026-11-08T15:00:00-05:00") or a local time of day ("15:00", today in
CHECKIN_TIMEZONE). Leave it unset in deployed environments.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Medication, MedicationLog, Patient

DEFAULT_TIMEZONE = "America/New_York"
ANSWERED = ("taken", "skipped")


# ---- clock ---------------------------------------------------------------------------

def local_zone() -> ZoneInfo:
    name = (os.getenv("CHECKIN_TIMEZONE") or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def now_utc() -> datetime:
    """The current time in UTC, or CHECKIN_NOW_OVERRIDE when set (tests and demos only)."""
    override = (os.getenv("CHECKIN_NOW_OVERRIDE") or "").strip()
    if override:
        zone = local_zone()
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", override)
        if m:
            today = datetime.now(zone).date()
            at = datetime.combine(today, time(int(m.group(1)), int(m.group(2))), tzinfo=zone)
            return at.astimezone(timezone.utc)
        try:
            at = datetime.fromisoformat(override)
        except ValueError:
            at = None
        if at is not None:
            if at.tzinfo is None:
                at = at.replace(tzinfo=zone)
            return at.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Stored dose times are UTC; SQLite returns them without a timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


# ---- which doses are due -------------------------------------------------------------

def _parse_hhmm(value: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*", str(value or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)), int(m.group(2))


def _active_on(med: Medication, day: date) -> bool:
    if not med.is_active:
        return False
    if med.start_date and day < med.start_date:
        return False
    return not (med.end_date and day > med.end_date)


def medication_plan(db: Session, patient: Patient, now: datetime | None = None) -> dict:
    """{'has_meds', 'has_scheduled', 'due': [...], 'as_needed': [...]} for the check-in.

    due: today's doses due at or before now with no taken/skipped log, oldest first, each
    {medication_id, name, dosage, scheduled_for (UTC ISO), hour, minute}.
    as_needed: [{medication_id, name, dosage}] for active medicines with no times of day.
    """
    now = _as_utc(now or now_utc())
    zone = local_zone()
    today = now.astimezone(zone).date()
    meds = db.scalars(select(Medication).where(Medication.patient_id == patient.id)
                      .order_by(Medication.name)).all()
    meds = [m for m in meds if _active_on(m, today)]
    scheduled = [m for m in meds if any(_parse_hhmm(t) for t in (m.times_of_day or []))]
    as_needed = [{"medication_id": str(m.id), "name": m.name, "dosage": m.dosage}
                 for m in meds if not (m.times_of_day or [])]

    due: list[dict] = []
    for med in scheduled:
        for value in med.times_of_day or []:
            hm = _parse_hhmm(value)
            if hm is None:
                continue
            at = datetime.combine(today, time(*hm), tzinfo=zone).astimezone(timezone.utc)
            if at <= now:
                due.append({"medication_id": str(med.id), "name": med.name, "dosage": med.dosage,
                            "scheduled_for": at.isoformat(), "hour": hm[0], "minute": hm[1]})
    if due:
        answered = answered_keys(db, [d["medication_id"] for d in due])
        due = [d for d in due if (d["medication_id"], d["scheduled_for"]) not in answered]
    due.sort(key=lambda d: (d["scheduled_for"], d["name"]))
    return {"has_meds": bool(meds), "has_scheduled": bool(scheduled), "due": due, "as_needed": as_needed}


def answered_keys(db: Session, medication_ids: list[str]) -> set[tuple[str, str]]:
    """(medication_id, scheduled_for UTC ISO) for doses already answered taken/skipped."""
    import uuid

    ids = {uuid.UUID(m) for m in medication_ids}
    if not ids:
        return set()
    since = now_utc() - timedelta(days=2)
    rows = db.scalars(select(MedicationLog).where(
        MedicationLog.medication_id.in_(ids), MedicationLog.status.in_(ANSWERED),
        MedicationLog.scheduled_for >= since)).all()
    return {(str(r.medication_id), _as_utc(r.scheduled_for).isoformat()) for r in rows}


def still_open(db: Session, doses: list[dict]) -> list[dict]:
    """The doses from a stored queue that nobody has answered meanwhile (for example on the dashboard)."""
    if not doses:
        return []
    answered = answered_keys(db, [d["medication_id"] for d in doses])
    return [d for d in doses if (d["medication_id"], d["scheduled_for"]) not in answered]


def record(db: Session, dose: dict, status: str) -> MedicationLog:
    """Upserts the dose's log row as taken or skipped (same rule as POST /medications/{id}/logs)."""
    import uuid

    med_id = uuid.UUID(dose["medication_id"])
    scheduled = _as_utc(datetime.fromisoformat(dose["scheduled_for"]))
    row = db.scalar(select(MedicationLog).where(MedicationLog.medication_id == med_id,
                                                MedicationLog.scheduled_for == scheduled))
    if row is None:
        row = MedicationLog(medication_id=med_id, scheduled_for=scheduled)
        db.add(row)
    row.status = status
    row.responded_at = datetime.now(timezone.utc)
    db.flush()
    return row


# ---- speech-friendly wording -----------------------------------------------------------

_ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def number_words(n: int) -> str:
    """0..999999 in words: 81 -> 'eighty-one', 1000 -> 'one thousand', 325 -> 'three hundred twenty-five'."""
    if n < 0:
        return "minus " + number_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return f"{_ONES[hundreds]} hundred" + (f" {number_words(rest)}" if rest else "")
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        return f"{number_words(thousands)} thousand" + (f" {number_words(rest)}" if rest else "")
    return str(n)


def _amount_words(text: str) -> str:
    if "." in text:
        whole, frac = text.split(".", 1)
        return f"{number_words(int(whole or 0))} point " + " ".join(_ONES[int(d)] for d in frac)
    return number_words(int(text))


_UNITS = {
    "mg": ("milligram", "milligrams"), "mcg": ("microgram", "micrograms"), "µg": ("microgram", "micrograms"),
    "g": ("gram", "grams"), "ml": ("milliliter", "milliliters"), "iu": ("unit", "units"),
    "units": ("unit", "units"), "unit": ("unit", "units"), "tablet": ("tablet", "tablets"),
    "tablets": ("tablet", "tablets"), "tab": ("tablet", "tablets"), "tabs": ("tablet", "tablets"),
    "capsule": ("capsule", "capsules"), "capsules": ("capsule", "capsules"), "cap": ("capsule", "capsules"),
    "caps": ("capsule", "capsules"), "pill": ("pill", "pills"), "pills": ("pill", "pills"),
    "puff": ("puff", "puffs"), "puffs": ("puff", "puffs"), "drop": ("drop", "drops"), "drops": ("drop", "drops"),
}


def spoken_dosage(dosage: str) -> str:
    """'1000 mg' -> 'one thousand milligrams'; '2.5 mg' -> 'two point five milligrams'.
    Anything it cannot read is returned without symbols."""
    text = (dosage or "").strip()

    def repl(m: re.Match) -> str:
        amount = m.group(1).replace(",", "")
        unit = (m.group(2) or "").lower()
        words = _amount_words(amount)
        if unit in _UNITS:
            singular, plural = _UNITS[unit]
            words += " " + (singular if amount in ("1", "1.0") else plural)
        elif unit:
            words += f" {m.group(2)}"
        return words

    out = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*([a-zA-Zµ]+)?", repl, text)
    return re.sub(r"[^\w\s'-]", " ", out).strip()


def spoken_time(hour: int, minute: int) -> str:
    """6:00 -> 'six this morning', 14:00 -> 'two this afternoon', 20:00 -> 'eight tonight'."""
    if hour == 12 and minute == 0:
        return "noon"
    if hour == 0 and minute == 0:
        return "midnight"
    h12 = hour % 12 or 12
    words = number_words(h12)
    if minute == 30:
        words += " thirty"
    elif minute:
        words += f" oh {number_words(minute)}" if minute < 10 else f" {number_words(minute)}"
    if hour < 12:
        part = "this morning"
    elif hour < 17:
        part = "this afternoon"
    elif hour < 20:
        part = "this evening"
    else:
        part = "tonight"
    return f"{words} {part}"


def short_time(hour: int, minute: int) -> str:
    """For the written summary: '8 AM', '2 PM', '6:30 PM'."""
    h12 = hour % 12 or 12
    suffix = "AM" if hour < 12 else "PM"
    return f"{h12}:{minute:02d} {suffix}" if minute else f"{h12} {suffix}"


def short_label(dose: dict) -> str:
    return f"{dose['name'].lower()} {short_time(dose['hour'], dose['minute'])}"


# ---- what the patient said about named medicines ------------------------------------------

ALIASES = {
    "acetaminophen": ("acetaminophen", "tylenol", "paracetamol"),
    "oxycodone": ("oxycodone", "oxy", "percocet", "oxycontin"),
    "aspirin": ("aspirin", "baby aspirin"),
}
_NOT_TAKEN = re.compile(r"\b(?:missed|miss|forgot|forget|forgotten|skipped|skip|didn't take|did not take|"
                        r"haven't taken|have not taken|didn't|did not|haven't|not yet|ran out|no)\b")
_TAKEN = re.compile(r"\b(?:took|taken|had|yes|yep|yeah|did|done|swallowed)\b")
_CLAUSES = re.compile(r"[,.;!?]|\bbut\b|\band\b|\bthen\b|\balso\b|\bwhile\b")


def _names_for(med_name: str) -> tuple[str, ...]:
    key = med_name.lower().split()[0] if med_name.strip() else ""
    return ALIASES.get(key, (key,)) if key else ()


def mentions(text: str, med_names: list[str]) -> list[dict]:
    """[{name, taken}] for medicines from med_names that the message says were taken or missed.

    "I took the acetaminophen but skipped the aspirin" -> acetaminophen taken, aspirin not.
    A clause naming a medicine without a verb inherits the previous clause's verb
    ("took the acetaminophen and the aspirin").
    """
    from app.services.foggy.lexicon import normalize

    # Questions report nothing ("can I take my aspirin later?"); statements around them still count.
    t = " . ".join(s for s in re.split(r"(?<=[.;!?])\s*", normalize(text)) if s and "?" not in s)
    out: dict[str, bool] = {}
    last: bool | None = None
    pending: list[str] = []
    for clause in _CLAUSES.split(t):
        named = [n for n in med_names if any(re.search(rf"\b{re.escape(a)}\b", clause) for a in _names_for(n))]
        if _NOT_TAKEN.search(clause):
            status: bool | None = False
        elif _TAKEN.search(clause):
            status = True
        else:
            status = None
        if status is not None:
            for n in pending:  # "the aspirin and I took the acetaminophen" is rare; earlier names take this verb
                out.setdefault(n, status)
            pending = []
            last = status
        for n in named:
            if status is not None:
                out[n] = status
            elif last is not None:
                out[n] = last
            else:
                pending.append(n)
    return [{"name": n, "taken": v} for n, v in out.items()]


def match_name(name: str, med_names: list[str]) -> str | None:
    """The patient's medicine that a classifier-extracted name refers to."""
    want = (name or "").strip().lower()
    if not want:
        return None
    for n in med_names:
        if any(re.search(rf"\b{re.escape(a)}\b", want) for a in _names_for(n)) or want == n.lower():
            return n
    return None
