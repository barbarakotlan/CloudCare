"""Outreach history and rate limits.

One text per patient per 60 s and one call per patient per 2 min. Every attempt that
reached the provider counts, success or not, so a double tap can never send twice.
The limit is enforced in memory (atomic within one server process) and from the
`outreach_log` table (survives restarts and spans processes). If the table hasn't been
created yet (database/outreach.sql not applied), the in-memory limit still holds and a
warning is logged instead of failing the request.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.outreach import OutreachLog

log = logging.getLogger("cloudcare.outreach")

_lock = threading.Lock()
_last_attempt: dict[tuple[uuid.UUID, str], float] = {}


def reset() -> None:
    """Tests only."""
    with _lock:
        _last_attempt.clear()


def _as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes (stored as UTC).
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _db_wait_seconds(db: Session, patient_id: uuid.UUID, channel: str, interval: int) -> int:
    try:
        last = db.scalar(
            select(OutreachLog.created_at)
            .where(OutreachLog.patient_id == patient_id, OutreachLog.channel == channel)
            .order_by(OutreachLog.created_at.desc())
            .limit(1)
        )
    except SQLAlchemyError as exc:
        db.rollback()
        log.warning("outreach.log.unavailable op=read type=%s", type(exc).__name__)
        return 0
    if last is None:
        return 0
    elapsed = (datetime.now(timezone.utc) - _as_utc(last)).total_seconds()
    return max(0, int(interval - elapsed + 0.999))


def reserve(db: Session, patient_id: uuid.UUID, channel: str, interval: int) -> int:
    """Claims the patient's next slot on this channel.

    Returns 0 when the caller may go ahead (the slot is now taken), otherwise the
    number of seconds to wait.
    """
    with _lock:
        now = time.monotonic()
        key = (patient_id, channel)
        last = _last_attempt.get(key)
        if last is not None and now - last < interval:
            return max(1, int(interval - (now - last) + 0.999))
        wait = _db_wait_seconds(db, patient_id, channel, interval)
        if wait > 0:
            return wait
        _last_attempt[key] = now
        return 0


def release(patient_id: uuid.UUID, channel: str) -> None:
    """Gives the slot back when nothing was sent to the provider (e.g. a config error)."""
    with _lock:
        _last_attempt.pop((patient_id, channel), None)


def record(
    db: Session,
    *,
    patient_id: uuid.UUID,
    kind: str,
    channel: str,
    to_last4: str,
    status: str,
    provider_id: str | None,
) -> uuid.UUID | None:
    """Writes one outreach_log row. Never raises: the action already happened."""
    row = OutreachLog(
        patient_id=patient_id,
        kind=kind,
        channel=channel,
        to_number_last4=to_last4,
        status=status,
        provider_id=(provider_id or None) and provider_id[:64],
    )
    try:
        db.add(row)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        log.warning("outreach.log.unavailable op=write type=%s", type(exc).__name__)
        return None
    log.info("outreach.%s.%s kind=%s to=...%s", channel, status, kind, to_last4)
    return row.id


def find_message(db: Session, patient_id: uuid.UUID, provider_id: str) -> OutreachLog | None:
    """The patient's own text with this Twilio SID, sent within the last day."""
    since = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        row = db.scalar(
            select(OutreachLog).where(
                OutreachLog.patient_id == patient_id,
                OutreachLog.channel == "sms",
                OutreachLog.provider_id == provider_id,
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        log.warning("outreach.log.unavailable op=read type=%s", type(exc).__name__)
        return None
    if row is None or _as_utc(row.created_at) < since:
        return None
    return row
