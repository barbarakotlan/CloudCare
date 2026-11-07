from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, get_db

app = FastAPI(title="CloudCare API")

# Let the Next.js frontend (localhost:3000) call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "CloudCare API is running"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Checks that the API is up and the database is reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": engine.dialect.name}
