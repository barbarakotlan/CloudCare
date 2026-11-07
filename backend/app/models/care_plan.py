import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._types import Embedding, created_at, uuid_pk


class CarePlan(Base):
    """Recovery instructions a clinician uploads for a patient."""

    __tablename__ = "care_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at()

    patient: Mapped["Patient"] = relationship(back_populates="care_plans")
    chunks: Mapped[list["CarePlanChunk"]] = relationship(
        back_populates="care_plan", cascade="all, delete-orphan", order_by="CarePlanChunk.chunk_index"
    )


class CarePlanChunk(Base):
    """A piece of a care plan (plus its embedding) that Foggy can retrieve and cite."""

    __tablename__ = "care_plan_chunks"
    __table_args__ = (UniqueConstraint("care_plan_id", "chunk_index"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    care_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("care_plans.id", ondelete="CASCADE"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Embedding)

    care_plan: Mapped[CarePlan] = relationship(back_populates="chunks")
