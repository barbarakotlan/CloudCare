"""Renders the onboarding-request email for the sales inbox and stores it.

Deliberately no delivery: there is no SMTP or email provider here, and the row keeps
status 'stored'. Someone on the team reads stored requests (GET /sales/leads) until a
real sender is chosen.
"""

import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import SalesEmail, SalesLead

DEFAULT_TO = "sales@cloudcare.icu"
SUBJECT_MAX = 200

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


def _one_line(value: str) -> str:
    """No line breaks in a subject (header injection is moot without a sender, but stay tidy)."""
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
    lines += ["", "Stored by the CloudCare API. Not sent automatically; reply to the contact directly."]
    return RenderedEmail(to=lead_to_address(), subject=subject, body="\n".join(lines))


def store(db: Session, lead: SalesLead) -> tuple[SalesEmail, RenderedEmail]:
    """Adds the rendered email row (status 'stored'). The caller commits."""
    email = render(lead)
    row = SalesEmail(lead_id=lead.id, to_address=email.to, subject=email.subject, body=email.body, status="stored")
    db.add(row)
    return row, email
