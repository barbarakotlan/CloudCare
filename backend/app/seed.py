"""Creates the demo login accounts if they don't exist yet. Runs on app startup."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User

DEMO_PASSWORD = "demo123"
DEMO_USERS = [
    {"email": "patient@demo.com", "full_name": "Jordan Lee", "role": "patient"},
    {"email": "clinician@demo.com", "full_name": "Dr. Priya Patel", "role": "clinician"},
]


def seed_demo_users(db: Session) -> None:
    for u in DEMO_USERS:
        if db.scalar(select(User).where(User.email == u["email"])) is None:
            db.add(User(**u, password_hash=hash_password(DEMO_PASSWORD)))
    db.commit()
