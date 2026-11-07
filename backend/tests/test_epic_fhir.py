"""Epic FHIR client, record normalization and /epic records routes.

Canned R4 and STU3 bundles stand in for Epic; httpx.MockTransport serves them.

Run from the repo root with either:
    .venv\\Scripts\\python.exe backend\\tests\\test_epic_fhir.py
    .venv\\Scripts\\python.exe -m pytest backend/tests   (if pytest is installed)
"""

import base64
import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import auth  # noqa: E402
from app import models  # noqa: E402,F401
from app.database import Base, get_db  # noqa: E402
from app.epic import config as epic_config  # noqa: E402
from app.epic import normalize, store  # noqa: E402
from app.epic.oauth import TokenSet, utcnow  # noqa: E402
from app.models import EpicConnection, User  # noqa: E402

HOST = "https://fhir.epic.com"
R4 = f"{HOST}/interconnect-fhir-oauth/api/FHIR/R4"
STU3 = f"{HOST}/interconnect-fhir-oauth/api/FHIR/STU3"
TOKEN = f"{HOST}/interconnect-fhir-oauth/oauth2/token"
PATIENT = "erXuFYUfucBZaryVksYEcMg3"
KEY = Fernet.generate_key().decode()

EPIC_ENV = (
    "EPIC_CLIENT_ID", "EPIC_CLIENT_SECRET", "EPIC_FHIR_BASE_URL", "EPIC_STU3_BASE_URL", "EPIC_REDIRECT_URI",
    "EPIC_SCOPES", "EPIC_TOKEN_ENCRYPTION_KEY", "EPIC_SANDBOX", "EPIC_LABS_FHIR_VERSION",
)


def configure(**overrides) -> None:
    for name in EPIC_ENV:
        os.environ.pop(name, None)
    values = {"EPIC_CLIENT_ID": "client", "EPIC_TOKEN_ENCRYPTION_KEY": KEY, "EPIC_FHIR_BASE_URL": R4}
    values.update(overrides)
    for name, value in values.items():
        if value is not None:
            os.environ[name] = value


def bundle(*resources, next_url: str | None = None) -> dict:
    out = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": r, "search": {"mode": "match"}} for r in resources],
    }
    if next_url:
        out["link"] = [{"relation": "next", "url": next_url}]
    return out


# ---- canned Epic data ----------------------------------------------------------------------------

MED_REQUEST_CONCEPT = {
    "resourceType": "MedicationRequest",
    "id": "mr1",
    "status": "active",
    "authoredOn": "2026-11-04",
    "medicationCodeableConcept": {"text": "oxyCODONE 5 MG tablet", "coding": [{"display": "Oxycodone"}]},
    "requester": {"display": "Priya Patel, MD"},
    "dosageInstruction": [
        {
            "text": "Take 1 tablet by mouth every 6 hours as needed for pain",
            "timing": {"repeat": {"frequency": 1, "period": 6, "periodUnit": "h"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "tablet"}}],
        }
    ],
}
MED_REQUEST_REFERENCE = {
    "resourceType": "MedicationRequest",
    "id": "mr2",
    "status": "completed",
    "authoredOn": "2026-10-01",
    "medicationReference": {"reference": "Medication/med-42"},
    "dosageInstruction": [{"timing": {"code": {"text": "Daily"}}, "doseAndRate": [{"doseQuantity": {"value": 81, "unit": "mg"}}]}],
}
MEDICATION_42 = {"resourceType": "Medication", "id": "med-42", "code": {"coding": [{"display": "Aspirin 81 MG chewable tablet"}]}}

LAB_STU3_QUANTITY = {
    "resourceType": "Observation",
    "id": "lab1",
    "status": "final",
    "category": [{"coding": [{"code": "laboratory"}]}],
    "code": {"text": "Hemoglobin"},
    "effectiveDateTime": "2026-11-05T08:00:00Z",
    "valueQuantity": {"value": 10.2, "unit": "g/dL"},
    "referenceRange": [{"low": {"value": 13.5, "unit": "g/dL"}, "high": {"value": 17.5, "unit": "g/dL"}}],
    "interpretation": {"coding": [{"code": "L", "display": "Low"}]},  # STU3: single CodeableConcept
    "context": {"reference": "Encounter/enc1"},  # STU3 name for R4's `encounter`
}
LAB_STU3_COMPONENTS = {
    "resourceType": "Observation",
    "id": "lab2",
    "status": "final",
    "code": {"coding": [{"display": "Basic metabolic panel"}]},
    "issued": "2026-11-03T10:00:00Z",
    "component": [
        {"code": {"text": "Sodium"}, "valueQuantity": {"value": 139, "unit": "mmol/L"},
         "referenceRange": [{"text": "135-145 mmol/L"}]},
        {"code": {"text": "Potassium"}, "valueQuantity": {"value": 4.1, "unit": "mmol/L"}},
    ],
}
LAB_STU3_STRING = {
    "resourceType": "Observation",
    "id": "lab3",
    "status": "preliminary",
    "code": {"text": "Urine culture"},
    "effectivePeriod": {"start": "2026-11-02T09:00:00Z"},
    "valueString": "No growth at 24 hours",
}
LAB_R4 = {
    "resourceType": "Observation",
    "id": "lab-r4",
    "status": "final",
    "code": {"text": "Glucose"},
    "effectiveDateTime": "2026-11-06T07:30:00Z",
    "valueQuantity": {"value": 182, "unit": "mg/dL"},
    "interpretation": [{"text": "High"}],  # R4: list of CodeableConcept
    "encounter": {"reference": "Encounter/enc1"},
}

ENCOUNTER_R4 = {
    "resourceType": "Encounter",
    "id": "enc1",
    "status": "finished",
    "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "inpatient"},
    "type": [{"text": "Hospital Encounter"}],
    "period": {"start": "2026-11-04T07:00:00Z", "end": "2026-11-05T15:00:00Z"},
    "location": [{"location": {"display": "Cloud General Hospital"}}],
    "reasonCode": [{"text": "Primary osteoarthritis of right knee"}],
}
ENCOUNTER_STU3_STYLE = {
    "resourceType": "Encounter",
    "id": "enc2",
    "class": {"code": "AMB"},
    "type": [{"coding": [{"display": "Office Visit"}]}],
    "period": {"start": "2026-10-20T14:00:00Z"},
    "reason": [{"text": "Pre-op visit"}],
}

NOTE_HTML_URL = {
    "resourceType": "DocumentReference",
    "id": "doc1",
    "docStatus": "final",
    "status": "current",
    "type": {"text": "Discharge Summary"},
    "date": "2026-11-05T16:00:00Z",
    "author": [{"display": "Priya Patel, MD"}],
    "content": [{"attachment": {"contentType": "text/html", "url": "Binary/note-1"}}],
}
NOTE_PDF = {
    "resourceType": "DocumentReference",
    "id": "doc2",
    "type": {"text": "Operative Note"},
    "date": "2026-11-04T12:00:00Z",
    "content": [{"attachment": {"contentType": "application/pdf", "url": "Binary/pdf-1"}}],
}
NOTE_INLINE_TEXT = {
    "resourceType": "DocumentReference",
    "id": "doc3",
    "description": "Nursing note",
    "context": {"period": {"start": "2026-11-03T08:00:00Z"}},
    "content": [{"attachment": {"contentType": "text/plain", "data": base64.b64encode(b"Patient ambulating.").decode()}}],
}
NOTE_HTML = (
    "<html><head><style>p{color:red}</style><script>alert('x')</script></head>"
    "<body><p>Keep incision <b>dry</b> for 48 hours.</p><p>Call if fever &gt; 101.</p></body></html>"
)


class FakeEpic:
    """Routes by URL path; each entry is a list of (status, body) served in order (last repeats)."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.routes: dict[str, list[tuple[int, object]]] = {}
        self.token_replies: list[tuple[int, dict]] = []

    def on(self, url: str, *replies):
        self.routes[url] = list(replies)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url).split("?")[0]
        if url == f"{R4}/.well-known/smart-configuration":
            return httpx.Response(200, json={"authorization_endpoint": f"{HOST}/a", "token_endpoint": TOKEN})
        if url == TOKEN:
            status, body = self.token_replies.pop(0) if self.token_replies else (400, {"error": "invalid_grant"})
            return httpx.Response(status, json=body)
        replies = self.routes.get(url)
        if not replies:
            return httpx.Response(404, json={"resourceType": "OperationOutcome"})
        status, body = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(body, str):
            return httpx.Response(status, text=body, headers={"content-type": "text/html"})
        return httpx.Response(status, json=body, headers={"content-type": "application/fhir+json"})

    def hits(self, url: str) -> list[httpx.Request]:
        return [r for r in self.requests if str(r.url).split("?")[0] == url]


def install_fake() -> FakeEpic:
    fake = FakeEpic()
    epic_config.set_transport(httpx.MockTransport(fake.handler))
    return fake


def full_epic(fake: FakeEpic) -> None:
    fake.on(f"{R4}/MedicationRequest", (200, bundle(MED_REQUEST_CONCEPT, MED_REQUEST_REFERENCE)))
    fake.on(f"{R4}/Medication/med-42", (200, MEDICATION_42))
    fake.on(f"{STU3}/Observation", (200, bundle(LAB_STU3_QUANTITY, LAB_STU3_COMPONENTS, LAB_STU3_STRING)))
    fake.on(f"{R4}/Encounter", (200, bundle(ENCOUNTER_R4, ENCOUNTER_STU3_STYLE)))
    fake.on(f"{R4}/DocumentReference", (200, bundle(NOTE_PDF, NOTE_HTML_URL, NOTE_INLINE_TEXT)))
    fake.on(f"{R4}/Binary/note-1", (200, NOTE_HTML))


def make_app():
    from app.main import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    with TestSession() as db:
        users = {
            "a": User(email="a@example.com", full_name="Pat A", role="patient", password_hash="x"),
            "b": User(email="b@example.com", full_name="Pat B", role="patient", password_hash="x"),
        }
        db.add_all(users.values())
        db.commit()
        headers = {k: {"Authorization": f"Bearer {auth.create_token(u)}"} for k, u in users.items()}
        ids = {k: u.id for k, u in users.items()}
    return client, TestSession, headers, ids


def connect(TestSession, user_id, *, access="ACCESS-1", refresh=None, expires_in=3600):
    with TestSession() as db:
        tokens = TokenSet(
            access_token=access,
            token_type="Bearer",
            expires_at=utcnow() + timedelta(seconds=expires_in),
            scope="openid patient/MedicationRequest.read",
            patient=PATIENT,
            refresh_token=refresh,
        )
        store.save_connection(db, epic_config.get_settings(), user_id, R4, tokens)


def connection(TestSession, user_id) -> EpicConnection | None:
    with TestSession() as db:
        conn = db.scalar(select(EpicConnection).where(EpicConnection.user_id == user_id))
        if conn is not None:
            db.expunge(conn)
        return conn


# ---- normalization -------------------------------------------------------------------------------------


def test_medication_from_codeable_concept():
    med = normalize.medication(MED_REQUEST_CONCEPT)
    assert med == {
        "name": "oxyCODONE 5 MG tablet",
        "dose_text": "Take 1 tablet by mouth every 6 hours as needed for pain",
        "frequency_text": "once every 6 hours",
        "status": "active",
        "authored_on": "2026-11-04",
        "prescriber": "Priya Patel, MD",
    }


def test_medication_from_reference_and_stu3_requester():
    med = normalize.medication(MED_REQUEST_REFERENCE, lambda ref: MEDICATION_42 if ref == "Medication/med-42" else None)
    assert med["name"] == "Aspirin 81 MG chewable tablet"
    assert med["dose_text"] == "81 mg" and med["frequency_text"] == "Daily"
    stu3 = dict(MED_REQUEST_CONCEPT, requester={"agent": {"display": "Dr. STU3"}})
    assert normalize.medication(stu3)["prescriber"] == "Dr. STU3"
    contained = {
        "resourceType": "MedicationRequest",
        "contained": [{"resourceType": "Medication", "id": "m", "code": {"text": "Cefazolin"}}],
        "medicationReference": {"reference": "#m"},
    }
    assert normalize.medication(contained)["name"] == "Cefazolin"
    assert normalize.medication({"resourceType": "MedicationRequest"})["name"] == "Unnamed medication"


def test_stu3_lab_quantity_range_and_single_interpretation():
    lab = normalize.lab(LAB_STU3_QUANTITY)
    assert lab == {
        "name": "Hemoglobin",
        "value": "10.2",
        "unit": "g/dL",
        "reference_range": "13.5-17.5 g/dL",
        "status": "final",
        "effective_at": "2026-11-05T08:00:00Z",
        "interpretation": "Low",
    }


def test_stu3_lab_components_and_strings():
    panel = normalize.lab(LAB_STU3_COMPONENTS)
    assert panel["name"] == "Basic metabolic panel"
    assert panel["value"] == "Sodium: 139 mmol/L; Potassium: 4.1 mmol/L"
    assert panel["unit"] is None
    assert panel["reference_range"] == "135-145 mmol/L"
    assert panel["effective_at"] == "2026-11-03T10:00:00Z"  # falls back to issued

    culture = normalize.lab(LAB_STU3_STRING)
    assert culture["value"] == "No growth at 24 hours" and culture["effective_at"] == "2026-11-02T09:00:00Z"


def test_r4_lab_interpretation_list():
    lab = normalize.lab(LAB_R4)
    assert lab["interpretation"] == "High" and lab["value"] == "182" and lab["unit"] == "mg/dL"
    absent = normalize.lab({"code": {"text": "X"}, "dataAbsentReason": {"text": "Specimen lost"}})
    assert absent["value"] == "Not available (Specimen lost)"


def test_encounters_r4_and_stu3_reason():
    assert normalize.encounter(ENCOUNTER_R4) == {
        "type": "Hospital Encounter",
        "class": "inpatient",
        "start": "2026-11-04T07:00:00Z",
        "end": "2026-11-05T15:00:00Z",
        "location": "Cloud General Hospital",
        "reason": "Primary osteoarthritis of right knee",
    }
    stu3 = normalize.encounter(ENCOUNTER_STU3_STYLE)
    assert stu3["class"] == "AMB" and stu3["type"] == "Office Visit" and stu3["reason"] == "Pre-op visit"
    assert stu3["end"] is None and stu3["location"] is None


def test_note_html_is_reduced_to_plain_text():
    text = normalize.note_plain_text(NOTE_HTML, "text/html")
    assert text == "Keep incision dry for 48 hours.\n\nCall if fever > 101."
    assert "<" not in text and "alert" not in text and "color" not in text
    note = normalize.note(NOTE_HTML_URL, text)
    assert note["title"] == "Discharge Summary" and note["author"] == "Priya Patel, MD"
    assert note["status"] == "final" and note["has_full_text"] is True
    long = normalize.note(NOTE_HTML_URL, "word " * 400)
    assert len(long["content_preview"]) <= 600 and long["has_full_text"] is False
    assert normalize.note(NOTE_PDF, None)["content_preview"] is None


# ---- records route -------------------------------------------------------------------------------------------


def test_records_happy_path_all_four_resources():
    configure()
    fake = install_fake()
    full_epic(fake)
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])

    res = client.get("/epic/records", headers=headers["a"])
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["missing"] == [] and data["missing_reasons"] == {}
    assert [m["name"] for m in data["medications"]] == ["oxyCODONE 5 MG tablet", "Aspirin 81 MG chewable tablet"]
    assert [lab["name"] for lab in data["labs"]] == ["Hemoglobin", "Basic metabolic panel", "Urine culture"]
    assert data["encounters"][0]["class"] == "inpatient"
    assert [n["title"] for n in data["notes"]] == ["Discharge Summary", "Operative Note", "Nursing note"]
    assert data["notes"][0]["content_preview"].startswith("Keep incision dry")
    assert data["notes"][1]["content_preview"] is None  # PDF: metadata only
    assert data["notes"][2]["content_preview"] == "Patient ambulating."

    # Searches use the patient's FHIR id and the right base per resource.
    (meds,) = fake.hits(f"{R4}/MedicationRequest")
    assert parse_qs(meds.url.query.decode()) == {"patient": [PATIENT]}
    (labs,) = fake.hits(f"{STU3}/Observation")
    assert parse_qs(labs.url.query.decode()) == {"patient": [PATIENT], "category": ["laboratory"]}
    (notes,) = fake.hits(f"{R4}/DocumentReference")
    assert parse_qs(notes.url.query.decode()) == {"patient": [PATIENT], "category": ["clinical-note"]}
    assert fake.hits(f"{R4}/Binary/pdf-1") == []
    for req in fake.requests:
        if "/api/FHIR/" in str(req.url) and ".well-known" not in str(req.url):
            assert req.headers["authorization"] == "Bearer ACCESS-1"
    assert fake.hits(f"{R4}/MedicationRequest")[0].headers["accept"] == "application/fhir+json"

    assert connection(TestSession, ids["a"]).last_sync_at is not None


def test_403_and_404_mark_resources_missing():
    configure()
    fake = install_fake()
    full_epic(fake)
    fake.on(f"{R4}/DocumentReference", (403, {"resourceType": "OperationOutcome"}))
    fake.on(f"{R4}/Encounter", (404, {"resourceType": "OperationOutcome"}))
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])

    data = client.get("/epic/records", headers=headers["a"]).json()
    assert sorted(data["missing"]) == ["encounters", "notes"]
    assert data["missing_reasons"] == {"notes": "forbidden", "encounters": "not_found"}
    assert data["notes"] == [] and data["encounters"] == []
    assert len(data["medications"]) == 2 and len(data["labs"]) == 3
    assert connection(TestSession, ids["a"]).status == "active"


def test_stu3_labs_fall_back_to_r4():
    configure()
    fake = install_fake()
    full_epic(fake)
    fake.on(f"{STU3}/Observation", (401, {}))  # not a revoke: STU3 only
    fake.on(f"{R4}/Observation", (200, bundle(LAB_R4)))
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])
    data = client.get("/epic/records", headers=headers["a"]).json()
    assert [lab["name"] for lab in data["labs"]] == ["Glucose"] and "labs" not in data["missing"]
    assert connection(TestSession, ids["a"]).status == "active"


def test_pagination_follows_next_links_on_base_only():
    configure()
    fake = install_fake()
    full_epic(fake)
    page2 = f"{R4}/Encounter-page2"
    fake.on(f"{R4}/Encounter", (200, bundle(ENCOUNTER_R4, next_url=page2)))
    fake.on(page2, (200, bundle(ENCOUNTER_STU3_STYLE, next_url="https://evil.example.com/steal")))
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])
    data = client.get("/epic/records", headers=headers["a"]).json()
    assert len(data["encounters"]) == 2
    assert not any("evil.example.com" in str(r.url) for r in fake.requests)


def test_refresh_on_401_then_retry_succeeds():
    configure(EPIC_CLIENT_SECRET="s3cret")
    fake = install_fake()
    full_epic(fake)
    fake.on(f"{R4}/MedicationRequest", (401, {}), (200, bundle(MED_REQUEST_CONCEPT)))
    fake.token_replies = [(200, {"access_token": "ACCESS-2", "token_type": "bearer", "expires_in": 3600,
                                 "refresh_token": "REFRESH-2", "scope": "openid"})]
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"], refresh="REFRESH-1")

    res = client.get("/epic/records", headers=headers["a"])
    assert res.status_code == 200, res.text
    assert [m["name"] for m in res.json()["medications"]] == ["oxyCODONE 5 MG tablet"]
    (refresh_req,) = [r for r in fake.requests if str(r.url) == TOKEN]
    assert parse_qs(refresh_req.content.decode()) == {"grant_type": ["refresh_token"], "refresh_token": ["REFRESH-1"]}
    retry = fake.hits(f"{R4}/MedicationRequest")[-1]
    assert retry.headers["authorization"] == "Bearer ACCESS-2"

    conn = connection(TestSession, ids["a"])
    settings = epic_config.get_settings()
    assert conn.status == "active"
    assert store.access_token(conn, settings) == "ACCESS-2"
    assert store.refresh_token(conn, settings) == "REFRESH-2"


def test_second_401_after_refresh_marks_revoked():
    configure(EPIC_CLIENT_SECRET="s3cret")
    fake = install_fake()
    full_epic(fake)
    fake.on(f"{R4}/MedicationRequest", (401, {}))
    fake.token_replies = [(200, {"access_token": "ACCESS-2", "token_type": "Bearer", "expires_in": 3600})]
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"], refresh="REFRESH-1")

    res = client.get("/epic/records", headers=headers["a"])
    assert res.status_code == 409 and "Reconnect" in res.json()["detail"]
    assert connection(TestSession, ids["a"]).status == "revoked"
    status = client.get("/epic/status", headers=headers["a"]).json()
    assert status["revoked"] is True and status["connected"] is False
    assert client.get("/epic/records", headers=headers["a"]).status_code == 409


def test_failed_refresh_marks_revoked():
    configure(EPIC_CLIENT_SECRET="s3cret")
    fake = install_fake()
    full_epic(fake)
    fake.on(f"{R4}/MedicationRequest", (401, {}))
    fake.token_replies = [(400, {"error": "invalid_grant"})]
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"], refresh="REFRESH-1")
    assert client.get("/epic/records", headers=headers["a"]).status_code == 409
    assert connection(TestSession, ids["a"]).status == "revoked"


def test_public_client_401_is_revoked_without_refresh():
    configure()
    fake = install_fake()
    full_epic(fake)
    fake.on(f"{R4}/MedicationRequest", (401, {}))
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])
    assert client.get("/epic/records", headers=headers["a"]).status_code == 409
    assert [r for r in fake.requests if str(r.url) == TOKEN] == []
    assert connection(TestSession, ids["a"]).status == "revoked"


def test_expired_token_refreshes_before_calling_epic():
    configure(EPIC_CLIENT_SECRET="s3cret")
    fake = install_fake()
    full_epic(fake)
    fake.token_replies = [(200, {"access_token": "ACCESS-2", "token_type": "Bearer", "expires_in": 3600})]
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"], refresh="REFRESH-1", expires_in=-5)
    assert client.get("/epic/records", headers=headers["a"]).status_code == 200
    assert all(r.headers.get("authorization") != "Bearer ACCESS-1" for r in fake.requests if "/api/FHIR/" in str(r.url))


def test_expired_token_without_refresh_is_revoked_without_calling_epic():
    configure()
    fake = install_fake()
    full_epic(fake)
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"], expires_in=-5)
    assert client.get("/epic/records", headers=headers["a"]).status_code == 409
    assert not any("/api/FHIR/R4/MedicationRequest" in str(r.url) for r in fake.requests)


# ---- isolation + disconnect -------------------------------------------------------------------------------------


def test_patient_isolation():
    configure()
    fake = install_fake()
    full_epic(fake)
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])

    status_b = client.get("/epic/status", headers=headers["b"]).json()
    assert status_b["connected"] is False and status_b["patient_fhir_id"] is None
    assert client.get("/epic/records", headers=headers["b"]).status_code == 404
    assert client.delete("/epic/connection", headers=headers["b"]).status_code == 404
    assert fake.hits(f"{R4}/MedicationRequest") == []

    assert connection(TestSession, ids["a"]) is not None
    assert client.get("/epic/status", headers=headers["a"]).json()["patient_fhir_id"] == PATIENT


def test_disconnect_deletes_the_row():
    configure()
    fake = install_fake()
    full_epic(fake)
    client, TestSession, headers, ids = make_app()
    connect(TestSession, ids["a"])

    res = client.delete("/epic/connection", headers=headers["a"])
    assert res.status_code == 204
    assert connection(TestSession, ids["a"]) is None
    assert client.get("/epic/status", headers=headers["a"]).json()["connected"] is False
    res = client.get("/epic/records", headers=headers["a"])
    assert res.status_code == 404 and res.json()["detail"] == "MyChart is not connected"
    assert client.delete("/epic/connection", headers=headers["a"]).status_code == 404


def test_records_need_a_logged_in_user():
    configure()
    install_fake()
    client, _, _, _ = make_app()
    assert client.get("/epic/records").status_code == 401
    assert client.get("/epic/status").status_code == 401


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
