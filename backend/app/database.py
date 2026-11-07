import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load backend/.env no matter which folder uvicorn is started from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Postgres in .env, e.g. postgresql+psycopg://user:pass@host:5432/dbname
# If it's not set, fall back to a local SQLite file so the app still runs.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or "sqlite:///./cloudcare.db"

# Supabase's Connect dialog hands out postgresql:// URLs; SQLAlchemy would pick
# psycopg2 for those, but this project installs psycopg 3.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]


def _connect_args(url: str) -> dict:
    parsed = make_url(url)
    args: dict = {}
    if parsed.drivername != "postgresql+psycopg":
        return args
    # Supabase transaction pooler (port 6543) can't keep prepared statements
    # between transactions, so turn psycopg's automatic preparing off there.
    if parsed.port == 6543:
        args["prepare_threshold"] = None
    # Hosted Supabase: always encrypt, even if the URL forgot ?sslmode=require.
    if (parsed.host or "").endswith(".supabase.com") or (parsed.host or "").endswith(".supabase.co"):
        if "sslmode" not in parsed.query:
            args["sslmode"] = "require"
    return args


engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Parent class for all SQLAlchemy models."""


def get_db():
    """FastAPI dependency: one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
