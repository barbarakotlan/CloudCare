"""Texts and calls CloudCare placed to a patient's own phone. Postgres DDL: database/outreach.sql.

Only the last four digits of the destination are stored; the full number lives on
`patients.phone`. No message text or call content is kept here.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._types import created_at, uuid_pk


class OutreachLog(Base):
    __tablename__ = "outreach_log"
    __table_args__ = (
        CheckConstraint("channel IN ('sms', 'call')", name="outreach_log_channel_check"),
        CheckConstraint("status IN ('sent', 'started', 'failed')", name="outreach_log_status_check"),
        Index("ix_outreach_log_patient_channel_created", "patient_id", "channel", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # 'checkin' | 'plan_summary'
    channel: Mapped[str] = mapped_column(String(8), nullable=False)  # 'sms' | 'call'
    to_number_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # 'sent' | 'started' | 'failed'
    # Twilio message SID (SM...) or ElevenLabs conversation id. Null when the provider gave none.
    provider_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at()
