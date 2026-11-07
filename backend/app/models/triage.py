import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._types import JsonList, created_at, uuid_pk


class SymptomLog(Base):
    """One patient check-in. The structured fields are also the ML model's inputs."""

    __tablename__ = "symptom_logs"
    __table_args__ = (
        CheckConstraint("source IN ('checkin', 'chat', 'voice')", name="symptom_logs_source_check"),
        CheckConstraint("pain_level BETWEEN 0 AND 10", name="symptom_logs_pain_check"),
        CheckConstraint("mobility_level BETWEEN 0 AND 4", name="symptom_logs_mobility_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source: Mapped[str] = mapped_column(String, default="checkin", nullable=False)
    pain_level: Mapped[int | None] = mapped_column(SmallInteger)
    temperature_f: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    wound_redness: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wound_drainage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    swelling: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nausea: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shortness_of_breath: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mobility_level: Mapped[int | None] = mapped_column(SmallInteger)  # 0 bedbound .. 4 normal
    free_text: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="symptom_logs")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('patient', 'assistant', 'clinician')", name="chat_messages_role_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JsonList, default=list, nullable=False)
    answered_from_plan: Mapped[bool | None] = mapped_column(Boolean)  # False = not in care plan
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = created_at()

    patient: Mapped["Patient"] = relationship(back_populates="chat_messages")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 1", name="risk_scores_score_check"),
        CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="risk_scores_level_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    symptom_log_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("symptom_logs.id", ondelete="SET NULL")
    )
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    top_factors: Mapped[list] = mapped_column(JsonList, default=list, nullable=False)
    created_at: Mapped[datetime] = created_at()

    patient: Mapped["Patient"] = relationship(back_populates="risk_scores")


class Escalation(Base):
    """The human-in-the-loop queue that clinicians review."""

    __tablename__ = "escalations"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('red_flag', 'high_risk', 'unanswered_question', 'patient_request')",
            name="escalations_trigger_check",
        ),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'emergency')", name="escalations_severity_check"),
        CheckConstraint("status IN ('open', 'acknowledged', 'resolved')", name="escalations_status_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    risk_score_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("risk_scores.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    clinician_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["Patient"] = relationship(back_populates="escalations")
