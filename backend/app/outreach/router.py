"""/outreach/* routes: Foggy texts or calls the signed-in patient's own phone.

Patient-only. The destination is always the number stored on the patient's own
profile; there is no way to pass a different number in. Nothing is sent when the
number is missing or isn't a usable mobile number (emergency and service numbers
are refused by app.outreach.phone).
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_patient, local_tokens_enabled
from app.database import get_db
from app.models import CarePlan, CarePlanChunk, Patient
from app.outreach import calls, guard, log as outreach_log, sms
from app.outreach.config import CALL_INTERVAL_SECONDS, SMS_INTERVAL_SECONDS, OutreachSettings, get_settings
from app.outreach.phone import is_usable_e164, last4
from app.outreach.schemas import (
    CallIn,
    CallOut,
    CapabilitiesOut,
    CapabilityLimits,
    SmsIn,
    SmsOut,
    SmsStatusOut,
)

log = logging.getLogger("cloudcare.outreach")

router = APIRouter(prefix="/outreach", tags=["outreach"])

SMS_NOT_CONFIGURED = "Texting isn't set up on this server yet."
CALL_NOT_CONFIGURED = "Phone calls aren't set up on this server yet."
NO_PHONE = "Add your mobile number first."
BAD_PHONE = "Your saved number can't receive texts or calls from CloudCare. Update it and try again."
COUNTRY_BLOCKED = "CloudCare can only text or call US numbers right now."
_SID = re.compile(r"^(SM|MM)[0-9a-fA-F]{32}$")


DEMO_ONLY = "Demo accounts can only call approved test numbers"
DEMO_EMAIL_DOMAIN = "@demo.com"


def _is_demo_account(patient: Patient) -> bool:
    """The shared demo logins are public, so anyone could point them at any phone."""
    email = (patient.user.email if patient.user else "") or ""
    return email.strip().lower().endswith(DEMO_EMAIL_DOMAIN)


def _demo_blocked(patient: Patient, settings: OutreachSettings) -> bool:
    """True when a demo account's stored number isn't in OUTREACH_DEMO_ALLOWLIST."""
    return _is_demo_account(patient) and bool(patient.phone) and not settings.demo_number_allowed(patient.phone)


def _destination(patient: Patient, settings: OutreachSettings) -> str:
    """The patient's own stored number, or a 409 explaining why it can't be used."""
    if not patient.phone:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_PHONE)
    if not is_usable_e164(patient.phone):
        raise HTTPException(status.HTTP_409_CONFLICT, BAD_PHONE)
    if not settings.country_allowed(patient.phone):
        raise HTTPException(status.HTTP_409_CONFLICT, COUNTRY_BLOCKED)
    if _demo_blocked(patient, settings):
        log.info("outreach.refused reason=demo_not_allowlisted to=...%s", last4(patient.phone))
        raise HTTPException(status.HTTP_403_FORBIDDEN, DEMO_ONLY)
    return patient.phone


def _too_soon(response_detail: str, wait: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"{response_detail} Please wait {wait} seconds.",
        headers={"Retry-After": str(wait)},
    )


NEW_NUMBER = "Your mobile number was just changed. For your safety, texts and calls to a new number start {minutes} minutes after the change."
DAILY_LIMIT = "You've reached today's limit for this. Try again tomorrow, or use the check-in on your dashboard."
BUSY = "Calls are busy right now."


def _abuse_checks(db: Session, patient: Patient, channel: str, to_number: str, settings: OutreachSettings) -> None:
    """Limits that stop the button being used against someone else's phone (guard.py).

    Numbers listed explicitly in OUTREACH_DEMO_ALLOWLIST belong to the team, so they skip
    the new-number wait and the daily caps (rehearsals and live demos call the same phones
    many times). The server-wide hourly cap still applies to them.
    """
    if not settings.demo_number_listed(to_number):
        wait = guard.new_number_wait(patient.id)
        if wait:
            minutes = max(1, round(guard.new_number_cooldown_seconds() / 60))
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, NEW_NUMBER.format(minutes=minutes),
                                headers={"Retry-After": str(wait)})
        if outreach_log.count_since(db, patient.id, channel, guard.DAY) >= guard.max_per_patient_per_day():
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, DAILY_LIMIT, headers={"Retry-After": "3600"})
        wait = guard.number_wait(channel, to_number)
        if wait:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, DAILY_LIMIT, headers={"Retry-After": str(wait)})
    if channel == "call":
        wait = guard.global_call_wait()
        if wait:
            raise _too_soon(BUSY, wait)


@router.get("/capabilities", response_model=CapabilitiesOut)
def capabilities(patient: Patient = Depends(get_current_patient)):
    settings = get_settings()
    reasons: dict[str, str] = {}
    if not settings.sms_configured:
        reasons["sms"] = SMS_NOT_CONFIGURED
    if not settings.call_configured:
        reasons["call"] = CALL_NOT_CONFIGURED
    usable = is_usable_e164(patient.phone)
    if not patient.phone:
        reasons.setdefault("phone", NO_PHONE)
    elif not usable:
        reasons.setdefault("phone", BAD_PHONE)
    elif not settings.country_allowed(patient.phone):
        reasons.setdefault("phone", COUNTRY_BLOCKED)
    demo_blocked = _demo_blocked(patient, settings)
    if demo_blocked:
        reasons.setdefault("call", DEMO_ONLY)
        reasons.setdefault("sms", DEMO_ONLY)
    return CapabilitiesOut(
        sms=settings.sms_configured and not demo_blocked,
        call=settings.call_configured and not demo_blocked,
        reasons=reasons,
        phone_on_file=bool(patient.phone),
        phone_last4=last4(patient.phone) or None,
        limits=CapabilityLimits(sms_seconds=SMS_INTERVAL_SECONDS, call_seconds=CALL_INTERVAL_SECONDS),
    )


def _plan_sections(db: Session, patient: Patient) -> list[str]:
    plan_id = db.scalar(select(CarePlan.id).where(CarePlan.patient_id == patient.id, CarePlan.is_active))
    if plan_id is None:
        return []
    rows = db.scalars(
        select(CarePlanChunk.section).where(CarePlanChunk.care_plan_id == plan_id).order_by(CarePlanChunk.chunk_index)
    ).all()
    seen: list[str] = []
    for section in rows:
        if section and section not in seen:
            seen.append(section)
    return seen


@router.post("/sms", response_model=SmsOut)
def send_text(body: SmsIn, patient: Patient = Depends(get_current_patient), db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.sms_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SMS_NOT_CONFIGURED)
    to_number = _destination(patient, settings)
    to_last4 = last4(to_number)
    _abuse_checks(db, patient, "sms", to_number, settings)

    wait = outreach_log.reserve(db, patient.id, "sms", SMS_INTERVAL_SECONDS)
    if wait:
        raise _too_soon("A text was just sent.", wait)
    guard.count_attempt("sms", to_number)

    text = sms.build_body(
        body.kind,
        patient.user.full_name,
        settings.public_app_url,
        _plan_sections(db, patient) if body.kind == "plan_summary" else None,
    )
    result = sms.send_sms(settings, to_number, text)
    outreach_log.record(
        db,
        patient_id=patient.id,
        kind=body.kind,
        channel="sms",
        to_last4=to_last4,
        status="sent" if result.ok else "failed",
        provider_id=result.provider_id,
    )
    if result.ok:
        return SmsOut(status="sent", provider_id=result.provider_id, to_last4=to_last4)
    return SmsOut(status="failed", provider_id=result.provider_id, to_last4=to_last4, detail=result.detail)


@router.get("/sms/{provider_id}", response_model=SmsStatusOut)
def text_status(provider_id: str, patient: Patient = Depends(get_current_patient), db: Session = Depends(get_db)):
    """Delivery status of one of the patient's own texts (from the last day)."""
    settings = get_settings()
    if not settings.sms_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SMS_NOT_CONFIGURED)
    if not _SID.match(provider_id) or outreach_log.find_message(db, patient.id, provider_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Text not found")
    result = sms.fetch_status(settings, provider_id)
    if result.provider_status is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, result.detail or "Couldn't check the text's status right now.")
    return SmsStatusOut(
        provider_id=provider_id,
        delivery=result.provider_status,
        failed=not result.ok,
        detail=result.detail,
    )


@router.post("/call", response_model=CallOut)
def start_call(body: CallIn, patient: Patient = Depends(get_current_patient), db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.call_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, CALL_NOT_CONFIGURED)
    if not local_tokens_enabled():
        # The call carries a short-lived CloudCare token; without a strong JWT_SECRET there is none.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, CALL_NOT_CONFIGURED)
    to_number = _destination(patient, settings)
    to_last4 = last4(to_number)
    _abuse_checks(db, patient, "call", to_number, settings)

    wait = outreach_log.reserve(db, patient.id, "call", CALL_INTERVAL_SECONDS)
    if wait:
        raise _too_soon("A call was just started.", wait)
    guard.count_attempt("call", to_number)

    result = calls.start_call(settings, patient.user, to_number)
    outreach_log.record(
        db,
        patient_id=patient.id,
        kind=body.kind,
        channel="call",
        to_last4=to_last4,
        status="started" if result.ok else "failed",
        provider_id=result.conversation_id,
    )
    if result.ok:
        return CallOut(status="started", conversation_id=result.conversation_id, to_last4=to_last4)
    return CallOut(status="failed", to_last4=to_last4, detail=result.detail)
