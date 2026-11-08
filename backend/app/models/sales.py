"""Onboarding requests from the public sales chat. Postgres DDL: backend/sales.sql.

A lead is the work contact a hospital visitor typed into the chat's onboarding form. The
email to the team inbox is rendered and stored next to it, and sent only when an email
provider key is configured (see app/sales/emailer.py). No patient data belongs here.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._types import JsonList, created_at, uuid_pk


class SalesLead(Base):
    __tablename__ = "sales_leads"
    __table_args__ = (Index("ix_sales_leads_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    created_at: Mapped[datetime] = created_at()
    session_id: Mapped[str | None] = mapped_column(Text)
    hospital: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    work_email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    discharges_per_month: Mapped[str | None] = mapped_column(Text)
    ehr: Mapped[str | None] = mapped_column(Text)
    service_lines: Mapped[str | None] = mapped_column(Text)
    timeline: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source_page: Mapped[str | None] = mapped_column(Text)
    # [{role, content}], at most 40 turns.
    transcript: Mapped[list | None] = mapped_column(JsonList)


class SalesEmail(Base):
    __tablename__ = "sales_emails"
    __table_args__ = (
        Index("ix_sales_emails_created_at", "created_at"),
        Index("ix_sales_emails_lead_id", "lead_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales_leads.id", ondelete="CASCADE"), nullable=False
    )
    to_address: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # 'stored': rendered and kept here (sending off, or not attempted yet).
    # 'sent': accepted by the email provider (provider_id holds its message id).
    # 'failed': the provider call failed (error holds a short reason); the request is still stored.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="stored", server_default="stored")
    provider_id: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
