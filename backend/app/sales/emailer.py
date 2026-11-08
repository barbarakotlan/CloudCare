"""Renders the onboarding-request email for the team inbox, stores it, and (optionally) sends it.

Every request is stored first (status 'stored'), so nothing is lost if delivery fails.
Delivery is switched on by RESEND_API_KEY: after the row is committed it is posted to
Resend's email API, and the row records the outcome ('sent' with the provider message id,
or 'failed' with a short error). Without the key there is no network call at all and the
team reads stored requests through GET /sales/leads.
"""

import logging
import os
from dataclasses import dataclass
from typing import Literal

import httpx
from sqlalchemy.orm import Session

from app.models import SalesEmail, SalesLead

log = logging.getLogger("cloudcare.sales")

DEFAULT_TO = "support@cloudcare.icu"
DEFAULT_FROM = "CloudCare <no-reply@cloudcare.icu>"
RESEND_URL = "https://api.resend.com/emails"
HTTP_TIMEOUT = httpx.Timeout(10.0)
SUBJECT_MAX = 200
ERROR_MAX = 200

Delivery = Literal["sent", "stored", "failed"]

FIELDS = (
    ("Hospital", "hospital"),
    ("Contact", "contact_name"),
    ("Role", "role"),
    ("Work email", "work_email"),
    ("Phone", "phone"),
    ("Discharges per month", "discharges_per_month"),
    ("EHR", "ehr"),
    ("Service lines", "service_lines"),
    ("Timeline", "timeline"),
    ("Notes", "notes"),
    ("Page", "source_page"),
    ("Chat session", "session_id"),
)


@dataclass(frozen=True)
class RenderedEmail:
    to: str
    subject: str
    body: str


def lead_to_address() -> str:
    return (os.getenv("SALES_LEAD_TO") or "").strip() or DEFAULT_TO


def from_address() -> str:
    return (os.getenv("SALES_EMAIL_FROM") or "").strip() or DEFAULT_FROM


def api_key() -> str:
    return (os.getenv("RESEND_API_KEY") or "").strip()


def sending_enabled() -> bool:
    return bool(api_key())


# ---- HTTP client -----------------------------------------------------------------
# Tests swap in an httpx.MockTransport here so nothing ever reaches the provider.

_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=HTTP_TIMEOUT, transport=_transport, follow_redirects=False)


# ---- rendering -------------------------------------------------------------------


def _one_line(value: str) -> str:
    """No line breaks in a subject (keeps headers tidy)."""
    return " ".join((value or "").split())


def render(lead: SalesLead) -> RenderedEmail:
    subject = _one_line(f"CloudCare pilot request — {lead.hospital}")[:SUBJECT_MAX]
    lines = ["New pilot request from the CloudCare website chat.", ""]
    for label, attr in FIELDS:
        value = getattr(lead, attr, None)
        lines.append(f"{label}: {value if value not in (None, '') else '(not given)'}")
    created = lead.created_at.isoformat() if lead.created_at else None
    if created:
        lines.append(f"Received: {created}")
    lines += ["", "Chat transcript:"]
    transcript = lead.transcript or []
    if not transcript:
        lines.append("(none)")
    for turn in transcript:
        who = "Assistant" if turn.get("role") == "assistant" else "Visitor"
        lines.append(f"{who}: {turn.get('content', '')}")
    if sending_enabled():
        lines += ["", "Sent by the CloudCare API. Reply to this email to reach the contact directly."]
    else:
        lines += ["", "Stored by the CloudCare API. Not sent automatically; reply to the contact directly."]
    return RenderedEmail(to=lead_to_address(), subject=subject, body="\n".join(lines))


def store(db: Session, lead: SalesLead) -> tuple[SalesEmail, RenderedEmail]:
    """Adds the rendered email row (status 'stored'). The caller commits."""
    email = render(lead)
    row = SalesEmail(lead_id=lead.id, to_address=email.to, subject=email.subject, body=email.body, status="stored")
    db.add(row)
    return row, email


# ---- delivery --------------------------------------------------------------------


def _provider_error(res: httpx.Response) -> str:
    detail = ""
    try:
        data = res.json()
        if isinstance(data, dict):
            detail = str(data.get("message") or data.get("name") or "")
    except ValueError:
        pass
    text = f"http {res.status_code}" + (f": {_one_line(detail)}" if detail else "")
    return text[:ERROR_MAX]


def send(email: RenderedEmail, reply_to: str | None) -> tuple[Delivery, str | None, str | None]:
    """Posts one email to Resend. Returns (delivery, provider_id, error); never raises.
    Without RESEND_API_KEY nothing is sent and no request is made."""
    key = api_key()
    if not key:
        return "stored", None, None
    payload: dict = {"from": from_address(), "to": [email.to], "subject": email.subject, "text": email.body}
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        with _http_client() as client:
            res = client.post(RESEND_URL, json=payload, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as exc:
        return "failed", None, type(exc).__name__[:ERROR_MAX]
    if res.status_code >= 300:
        return "failed", None, _provider_error(res)
    provider_id = None
    try:
        data = res.json()
        if isinstance(data, dict) and data.get("id"):
            provider_id = str(data["id"])[:200]
    except ValueError:
        pass
    return "sent", provider_id, None


def deliver(db: Session, row: SalesEmail, email: RenderedEmail, reply_to: str | None) -> Delivery:
    """Sends a stored, committed email row and records the outcome on it. Never raises:
    a delivery problem leaves the request stored and is reported as 'failed'."""
    if not sending_enabled():
        return "stored"
    try:
        delivery, provider_id, error = send(email, reply_to)
    except Exception as exc:  # noqa: BLE001  (the lead is already stored)
        delivery, provider_id, error = "failed", None, type(exc).__name__[:ERROR_MAX]
    try:
        row.status = delivery
        row.provider_id = provider_id
        row.error = error
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.warning("sales.email.status_not_recorded reason=%s", type(exc).__name__)
    log.info("sales.email.delivery result=%s", delivery)
    return delivery
