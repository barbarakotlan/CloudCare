import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._types import JsonList, created_at, uuid_pk


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('patient', 'clinician')", name="users_role_check"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'patient' | 'clinician'
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()

    patient: Mapped["Patient | None"] = relationship(
        back_populates="user", foreign_keys="Patient.user_id", uselist=False
    )


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    clinician_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    procedure_name: Mapped[str] = mapped_column(Text, nullable=False)
    procedure_type: Mapped[str] = mapped_column(Text, nullable=False)
    surgery_date: Mapped[date] = mapped_column(Date, nullable=False)
    discharge_date: Mapped[date | None] = mapped_column(Date)
    comorbidities: Mapped[list] = mapped_column(JsonList, default=list, nullable=False)
    # Mobile number in E.164 (e.g. +15551234567). Postgres: database/patient_phone.sql.
    phone: Mapped[str | None] = mapped_column(Text)
    # Set only once the number has been confirmed (no confirmation flow yet, so null for now).
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()

    user: Mapped[User] = relationship(back_populates="patient", foreign_keys=[user_id])
    clinician: Mapped[User | None] = relationship(foreign_keys=[clinician_id])
    care_plans: Mapped[list["CarePlan"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    medications: Mapped[list["Medication"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    symptom_logs: Mapped[list["SymptomLog"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    risk_scores: Mapped[list["RiskScore"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    escalations: Mapped[list["Escalation"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
