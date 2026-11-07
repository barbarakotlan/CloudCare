"""Column types that work on both Postgres (real DB) and SQLite (local fallback)."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

# JSONB on Postgres, plain JSON on SQLite.
JsonList = JSON().with_variant(JSONB(), "postgresql")

# Must match vector(1024) in database/scheme.sql and your embedding model.
EMBEDDING_DIM = 1024
Embedding = JSON().with_variant(Vector(EMBEDDING_DIM), "postgresql")


def uuid_pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def created_at():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
