import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registers all tables on Base)
from app import epic
from app.database import Base, SessionLocal, engine, get_db
from app.outreach.router import router as outreach_router
from app.routes import auth, chat, demo, escalations, patients, recovery, symptoms
from app.sales.router import router as sales_router
from app.security import MAX_BODY_BYTES, BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.seed import seed_demo_users

log = logging.getLogger("cloudcare.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local SQLite fallback: create tables automatically.
    # Postgres: tables come from database/scheme.sql instead.
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo_users(db)
    yield


app = FastAPI(title="CloudCare API", lifespan=lifespan)

# Let the Next.js frontend call this API. CORS_ORIGINS is comma-separated.
DEFAULT_CORS_ORIGINS = "http://localhost:3000,https://cloudcare.icu,https://www.cloudcare.icu"
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in (os.getenv("CORS_ORIGINS") or DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

# The browser sends a bearer token in Authorization, never cookies, so credentials stay off:
# a stray origin in CORS_ORIGINS can't ride on a cookie session, and "*" can't be combined
# with credentials by mistake.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)
# Outermost last: headers are added to every response, including CORS preflights and 413s.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """Never send a stack trace or exception text to the client; the log keeps the details."""
    log.exception("unhandled.error path=%s", request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(symptoms.router)
app.include_router(chat.router)
app.include_router(escalations.router)
app.include_router(recovery.router)
app.include_router(epic.router)
app.include_router(outreach_router)
app.include_router(demo.router)
app.include_router(sales_router)


@app.get("/")
def root():
    return {"message": "CloudCare API is running"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Checks that the API is up and the database is reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": engine.dialect.name}
