"""Demo seed against a mocked Supabase Admin API (no network).

Run from the repo root:
    .venv\\Scripts\\python.exe backend\\tests\\test_seed_supabase.py
"""

import json
import os
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app import seed  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import Patient, User  # noqa: E402

PATIENT_ID = str(uuid.uuid4())
CLINICIAN_ID = str(uuid.uuid4())


class FakeAdminApi:
    """Patient is new (201); clinician already exists without a role (422 then lookup + PUT)."""

    def __init__(self):
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/auth/v1/admin/users":
            body = json.loads(request.content)
            if body["email"] == "patient@demo.com":
                return httpx.Response(201, json={"id": PATIENT_ID, "email": body["email"]})
            return httpx.Response(
                422, json={"code": 422, "error_code": "email_exists", "msg": "already been registered"}
            )
        if request.method == "GET" and path == "/auth/v1/admin/users":
            return httpx.Response(
                200, json={"users": [{"id": CLINICIAN_ID, "email": "clinician@demo.com", "app_metadata": {}}]}
            )
        if request.method == "PUT" and path == f"/auth/v1/admin/users/{CLINICIAN_ID}":
            return httpx.Response(200, json={"id": CLINICIAN_ID})
        return httpx.Response(404)


def _patch(fake: FakeAdminApi, key: str):
    seed.SUPABASE_URL = "https://example-ref.supabase.co"
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = key
    real_client = httpx.Client

    def client_with_mock(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake)
        return real_client(*args, **kwargs)

    seed.httpx.Client = client_with_mock
    return real_client


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)()


def test_seed_creates_supabase_users_and_aligns_local_ids():
    fake = FakeAdminApi()
    real_client = _patch(fake, "sb_secret_test_value")
    try:
        db = _session()
        seed.seed_demo_users(db)
        seed.seed_demo_users(db)  # idempotent
    finally:
        seed.httpx.Client = real_client

    patient = db.scalar(select(User).where(User.email == "patient@demo.com"))
    clinician = db.scalar(select(User).where(User.email == "clinician@demo.com"))
    assert str(patient.id) == PATIENT_ID
    assert str(clinician.id) == CLINICIAN_ID
    assert db.scalar(select(Patient).where(Patient.user_id == patient.id)).clinician_id == clinician.id
    assert len(db.scalars(select(User)).all()) == 2

    first_post = fake.requests[0]
    assert first_post.headers["apikey"] == "sb_secret_test_value"
    assert "authorization" not in first_post.headers  # new secret keys are not JWTs
    assert json.loads(first_post.content)["app_metadata"] == {"role": "patient"}
    puts = [r for r in fake.requests if r.method == "PUT"]
    assert puts and json.loads(puts[0].content) == {"app_metadata": {"role": "clinician"}}


def test_legacy_service_role_key_also_sent_as_bearer():
    fake = FakeAdminApi()
    real_client = _patch(fake, "eyJhbGciOiJIUzI1NiJ9.legacy.key")
    try:
        seed.ensure_supabase_demo_users(_session())
    finally:
        seed.httpx.Client = real_client
    assert fake.requests[0].headers["authorization"] == "Bearer eyJhbGciOiJIUzI1NiJ9.legacy.key"


def test_existing_local_rows_keep_their_ids():
    fake = FakeAdminApi()
    db = _session()
    os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    seed.SUPABASE_URL = ""
    seed.seed_demo_users(db)  # plain SQLite seed first: random ids
    original = {u.email: u.id for u in db.scalars(select(User))}

    real_client = _patch(fake, "sb_secret_test_value")
    try:
        ids = seed.ensure_supabase_demo_users(db)
        seed.seed_demo_users(db)
    finally:
        seed.httpx.Client = real_client
    assert ids["patient@demo.com"] == uuid.UUID(PATIENT_ID)
    assert {u.email: u.id for u in db.scalars(select(User))} == original


def test_admin_api_down_does_not_break_startup():
    def boom(request):
        raise httpx.ConnectError("no route to host", request=request)

    real_client = _patch(boom, "sb_secret_test_value")  # type: ignore[arg-type]
    try:
        db = _session()
        seed.seed_demo_users(db)
    finally:
        seed.httpx.Client = real_client
    assert len(db.scalars(select(User)).all()) == 2


def test_no_env_means_no_calls():
    os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    seed.SUPABASE_URL = ""
    assert seed.ensure_supabase_demo_users(_session()) == {}


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
