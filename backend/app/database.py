import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load backend/.env no matter which folder uvicorn is started from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Postgres in .env, e.g. postgresql+psycopg://user:pass@host:5432/dbname
# If it's not set, fall back to a local SQLite file so the app still runs.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cloudcare.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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
