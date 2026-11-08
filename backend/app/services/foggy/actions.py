"""External actions Foggy can take, behind application checks.

A generated sentence can never send anything: only the router calls these functions, and
each one checks capability, recipient, the patient's agreement to that specific action,
and duplicates before writing a row. Messaging the care team means an Escalation row in
the clinician queue (trigger "patient_request"); there is no phone or emergency calling.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Escalation, Patient
from app.schemas import SymptomIn

log = logging.getLogger("cloudcare.foggy")

# What this deployment can really do. The chat UI and voice agent read it from
# GET /chat/capabilities, and replies never offer anything listed as False.
CAPABILITIES = {
    "message_care_team": True,       # Escalation row in the clinician queue
    "call_care_team": False,         # no phone integration
    "emergency_call_assist": False,  # Foggy never places or starts emergency calls
    "simulated": False,              # real rows; the landing-page demo uses its own labeled engine
}

DUPLICATE_WINDOW = timedelta(minutes=5)
SUMMARY_MAX = 500


def capabilities() -> dict:
    return dict(CAPABILITIES)


class TurnActions:
    """Actions for one chat turn. Each kind runs at most once per turn."""

    def __init__(self, db: Session, patient: Patient, chat_message_id):
        self.db = db
        self.patient = patient
        self.chat_message_id = chat_message_id
        self.done: dict[str, dict] = {}
        self.escalated = False  # a real Escalation row was created this turn

    # ---- message the care team (needs agreement) ------------------------------------

    def message_care_team(self, pending: dict, consent: str) -> dict:
        """Sends the pending message after the patient agreed to it. Returns an action_result."""
        kind = "message_care_team"
        if kind in self.done:
            return self.done[kind]
        result = self._message_care_team(pending, consent)
        self.done[kind] = result
        log.info("foggy.action kind=%s status=%s", kind, result["status"])
        return result

    def _message_care_team(self, pending: dict, consent: str) -> dict:
        if not CAPABILITIES["message_care_team"]:
            return {"kind": "message_care_team", "status": "failed", "detail": "Messaging is not available."}
        if consent != "yes" or pending.get("kind") != "message_care_team" or pending.get("recipient") != "care_team":
            return {"kind": "message_care_team", "status": "failed", "detail": "No agreement to this action."}
        words = (pending.get("patient_words") or "").strip()[:SUMMARY_MAX] or "Patient asked to contact the care team."
        severity = "high" if pending.get("origin_route") == "CALL_SURGEON" else "low"
        try:
            origin_id = uuid.UUID(pending["chat_message_id"]) if pending.get("chat_message_id") else None
        except (ValueError, TypeError):
            origin_id = None
        try:
            if self._recent_duplicate("patient_request", words):  # a retried "yes" never sends twice
                return {"kind": "message_care_team", "status": "sent", "detail": "Already in the care team's queue."}
            with self.db.begin_nested():  # a failed insert must not lose the rest of the turn
                self.db.add(Escalation(
                    patient_id=self.patient.id, trigger_type="patient_request", severity=severity,
                    chat_message_id=origin_id or self.chat_message_id, summary=words,
                ))
                self.db.flush()
        except Exception as e:  # noqa: BLE001  (report failure truthfully, never a fake success)
            log.warning("foggy.action message_care_team failed (%s)", type(e).__name__)
            return {"kind": "message_care_team", "status": "failed", "detail": "The message could not be saved."}
        self.escalated = True
        return {"kind": "message_care_team", "status": "sent", "detail": "Added to the care team's queue."}

    # ---- emergency alert (dashboard event; no consent needed, no claim of contact) ------

    def emergency_alert(self, message: str) -> bool:
        """Red-flag escalation for the clinician dashboard. True if a new row was created."""
        if "emergency_alert" in self.done:
            return False
        summary = f'Possible emergency. Patient said: "{message.strip()[:SUMMARY_MAX]}"'
        self.done["emergency_alert"] = {}
        if self._recent_duplicate("red_flag", summary):
            return False
        self.db.add(Escalation(
            patient_id=self.patient.id, trigger_type="red_flag", severity="emergency",
            chat_message_id=self.chat_message_id, summary=summary,
        ))
        self.db.flush()
        self.escalated = True
        log.info("foggy.action kind=emergency_alert status=created")
        return True

    # ---- check-in ----------------------------------------------------------------

    # ---- dose answers from the check-in (the patient's own record, like the dashboard's buttons) ----

    def log_dose(self, dose: dict, status: str) -> None:
        """Marks one scheduled dose taken or skipped, as the patient said in the check-in."""
        from app.services.foggy import doses  # imported here to keep this module's imports light

        if status not in ("taken", "skipped"):
            return
        doses.record(self.db, dose, status)
        log.info("foggy.action kind=dose_log status=%s", status)

    def save_checkin(self, answers: dict, source: str, meds_summary: str | None = None) -> dict:
        """SymptomLog + risk score (+ high_risk escalation) through the same path as POST /symptoms.

        meds_summary: the medicine answers in plain words ("Missed: aspirin 8 AM. Taken: ...");
        without it the single medicines answer is written as before.
        """
        from app.routes.symptoms import record_checkin  # shared helper; imported here to avoid a cycle

        if "checkin" in self.done:
            return self.done["checkin"]
        detail = []
        meds = answers.get("meds_taken")
        if meds_summary:
            detail.append(meds_summary)
        elif meds:
            note = answers.get("meds_detail")
            detail.append(f"Medicines taken as planned: {meds}" + (f" ({note})" if note else ""))
        if answers.get("numbness"):
            detail.append(f"New numbness, tingling or color change: {answers['numbness']}")
        if answers.get("fall"):
            detail.append(f"Falls: {answers['fall']}")
        body = SymptomIn(
            pain_level=int(answers.get("pain", 0)),
            free_text=("Foggy check-in. " + ". ".join(d.rstrip(".") for d in detail) + ".")[:2000]
            if detail else "Foggy check-in.",
            source="voice" if source == "voice" else "chat",
        )
        symptom_log, risk, escalated = record_checkin(self.db, self.patient, body)
        self.db.flush()
        if escalated:
            self.escalated = True
        result = {"symptom_log_id": str(symptom_log.id), "risk_level": risk.risk_level, "escalated": escalated}
        self.done["checkin"] = result
        log.info("foggy.action kind=checkin risk=%s escalated=%s", risk.risk_level, escalated)
        return result

    # ---- helpers ------------------------------------------------------------------

    def _recent_duplicate(self, trigger: str, summary: str) -> bool:
        since = datetime.now(timezone.utc) - DUPLICATE_WINDOW
        rows = self.db.scalars(
            select(Escalation).where(
                Escalation.patient_id == self.patient.id, Escalation.trigger_type == trigger,
                Escalation.summary == summary, Escalation.status == "open",
            )
        ).all()
        for row in rows:
            created = row.created_at
            if created is None:
                return True
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= since:
                return True
        return False
