"""Load and save the per-patient chat_sessions row (pending offer and check-in progress)."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import ChatSession

CHECKIN_TTL = timedelta(hours=6)  # an abandoned check-in is dropped after this


def load(db: Session, patient_id) -> dict:
    """{'pending_action': dict|None, 'checkin_state': dict|None} (copies; safe to change)."""
    row = db.get(ChatSession, patient_id)
    if row is None:
        return {"pending_action": None, "checkin_state": None}
    # Deep copies: the check-in holds nested dicts (the medicine queue), and changing the loaded
    # JSON in place would hide the change from the database session.
    checkin = copy.deepcopy(row.checkin_state) if row.checkin_state else None
    if checkin and _expired(checkin):
        checkin = None
    return {
        "pending_action": copy.deepcopy(row.pending_action) if row.pending_action else None,
        "checkin_state": checkin,
    }


def save(db: Session, patient_id, pending_action: dict | None, checkin_state: dict | None) -> None:
    row = db.get(ChatSession, patient_id)
    if row is None:
        row = ChatSession(patient_id=patient_id)
        db.add(row)
    # New objects each time so the JSON columns are always detected as changed.
    row.pending_action = copy.deepcopy(pending_action) if pending_action else None
    row.checkin_state = copy.deepcopy(checkin_state) if checkin_state else None
    row.updated_at = datetime.now(timezone.utc)


def _expired(checkin: dict) -> bool:
    started = checkin.get("started_at")
    if not started:
        return False
    try:
        at = datetime.fromisoformat(started)
    except ValueError:
        return True
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - at > CHECKIN_TTL
