"""Foggy's per-patient conversation state. Postgres DDL: database/chat_state.sql."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._types import JsonList  # JSON on SQLite, JSONB on Postgres (any JSON value)


class ChatSession(Base):
    """One row per patient: the contact offer waiting for an answer and the check-in in progress.

    Text and voice share this row, so a "yes" spoken to the voice agent answers an offer
    made in the chat window and the reverse.
    """

    __tablename__ = "chat_sessions"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True
    )
    # {"kind": "message_care_team", "recipient": "care_team", "reason", "origin_route",
    #  "patient_words", "chat_message_id", "asked_again"} or null
    pending_action: Mapped[dict | None] = mapped_column(JsonList, nullable=True)
    # {"awaiting": "pain"|"meds_taken"|"numbness"|"fall", "answers": {...}, "clarifying": str|null,
    #  "first": bool, "started_at": iso} or null
    checkin_state: Mapped[dict | None] = mapped_column(JsonList, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
