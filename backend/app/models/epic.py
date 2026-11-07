"""Epic MyChart (SMART on FHIR) connection state. Postgres DDL: database/epic.sql."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models._types import created_at, uuid_pk


class EpicOAuthState(Base):
    """One pending authorize request. Single use, expires after 10 minutes."""

    __tablename__ = "epic_oauth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_verifier: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet-encrypted
    iss: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class EpicConnection(Base):
    """A patient's MyChart link. Tokens are Fernet-encrypted; one row per user."""

    __tablename__ = "epic_connections"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="epic_connections_status_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    iss: Mapped[str] = mapped_column(Text, nullable=False)
    patient_fhir_id: Mapped[str] = mapped_column(String(64), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Bearer")
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    id_token_sub: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
