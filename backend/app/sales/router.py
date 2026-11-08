"""/sales/*: the public sales chat ("talk to Barbara") and stored onboarding requests.

- POST /sales/chat   public. One reply in Barbara's voice (her AI twin) from the product
                     brief, through the language model when available, else keyword rules.
                     Never 500s: any model problem falls back to rules.
- POST /sales/leads  public. Stores an onboarding request and the rendered email to the
                     sales inbox (status 'stored'; nothing is sent).
- GET  /sales/leads  clinicians only. Stored requests, newest first.

Logs carry event names and counts only, never what visitors typed.
"""

import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_clinician
from app.database import get_db
from app.models import SalesEmail, SalesLead, User
from app.sales import emailer, prompt, rules
from app.sales.schemas import (
    TRANSCRIPT_KEEP,
    SalesChatIn,
    SalesChatOut,
    SalesLeadCreated,
    SalesLeadIn,
    SalesLeadOut,
)
from app.security import RateLimiter, too_many
from app.services import ai_service

log = logging.getLogger("cloudcare.sales")

router = APIRouter(prefix="/sales", tags=["sales"])

CHAT_LIMIT = RateLimiter("sales-chat", limit=20, window=60)
LEADS_LIMIT = RateLimiter("sales-leads", limit=5, window=3600)
# Server-wide budget for model calls. X-Forwarded-For can be forged, so a flood with
# rotating addresses gets keyword answers instead of spending the model quota.
MODEL_BUDGET = RateLimiter("sales-model", limit=120, window=60)

MAX_SENTENCES = 3
MAX_SUGGESTIONS = 3
SUGGESTION_MAX_CHARS = 60
LEADS_LIST_LIMIT = 500


# ---- client address and limits ---------------------------------------------------------


def sales_client_ip(request: Request) -> str:
    """First X-Forwarded-For hop when present (the visitor as the first proxy saw them),
    else the socket peer. Good enough for a per-visitor limit on public routes; the model
    budget above covers forged headers."""
    forwarded = request.headers.get("x-forwarded-for", "")
    for hop in forwarded.split(","):
        hop = hop.strip()
        if hop:
            return hop[:64]
    return request.client.host if request.client else "unknown"


def limit_sales_chat(request: Request) -> None:
    wait = CHAT_LIMIT.hit(sales_client_ip(request))
    if wait:
        raise too_many("You're sending messages very quickly.", wait)


def limit_sales_leads(request: Request) -> None:
    wait = LEADS_LIMIT.hit(sales_client_ip(request))
    if wait:
        raise too_many("Too many requests from this network.", wait)


# ---- reply clean-up (applies to model and rules alike) ---------------------------------

_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(]?[A-Z0-9])")
_ABBREV = re.compile(r"\b(Dr|Mr|Mrs|Ms|St|vs|approx|e\.g|i\.e)\.$", re.IGNORECASE)
_MARKDOWN = re.compile(r"(\*\*|__|`|^#+\s*|^\s*[-*•]\s+)", re.MULTILINE)
# Money amounts, and per-unit rates when the text is talking about money.
_MONEY = re.compile(
    r"[$€£]\s?\d|\b\d[\d,.]*\s?(k|thousand|million)?\s?(dollars|usd|eur|euros)\b",
    re.IGNORECASE,
)
_RATE = re.compile(r"\b\d[\d,.]*\s?k?\s?(per|a|/)\s?(month|mo|year|yr|patient|discharge|bed|seat|user|license)\b",
                   re.IGNORECASE)
_MONEY_WORDS = re.compile(r"\b(cost|costs|price|priced|pricing|fee|fees|charge|charges|pay|billed|subscription)\b",
                          re.IGNORECASE)
_FREE_PERIOD = re.compile(r"\bfree (pilot|trial|of charge)\b|\bno cost\b|\bat no charge\b|\bdiscount\w*\b",
                          re.IGNORECASE)
# Claims the brief says are not true today, unless negated just before.
_CLAIM = re.compile(r"\b(hipaa[- ](compliant|certified|ready)|fda[- ](cleared|approved|clearance|approval)|soc ?2[- ]?(compliant|certified))\b",
                    re.IGNORECASE)
_NEGATION = re.compile(r"\bnot\b|n't\b|\bno\b|\bnever\b|\byet to\b|\bwithout\b", re.IGNORECASE)


def has_price(text: str) -> bool:
    return bool(
        _MONEY.search(text)
        or _FREE_PERIOD.search(text)
        or (_RATE.search(text) and _MONEY_WORDS.search(text))
    )

PRICE_REPLY = f"We don't publish a price: {prompt.PRICING_RULE[0].lower()}{prompt.PRICING_RULE[1:]}"
CLAIM_REPLY = (
    "To be straight with you: CloudCare isn't operating under HIPAA yet, we have no BAAs with our vendors, "
    "and it hasn't been reviewed by the FDA."
)


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in _SPLIT.split((text or "").strip()):
        part = part.strip()
        if not part:
            continue
        if out and _ABBREV.search(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def _plain(text: str) -> str:
    return " ".join(_MARKDOWN.sub("", text or "").split())


def _unsupported_claim(text: str) -> bool:
    for match in _CLAIM.finditer(text):
        before = text[max(0, match.start() - 30):match.start()]
        if not _NEGATION.search(before):
            return True
    return False


def finalize(reply: str, suggestions: list, cta: bool) -> tuple[str, list[str]]:
    """Plain text, no price, no false compliance claim, at most three sentences; when the
    call to action fires, the last sentence is the onboarding invite."""
    text = _plain(reply)
    if has_price(text):
        text = PRICE_REPLY
    elif _unsupported_claim(text):
        text = CLAIM_REPLY
    # The invite is added by code (once, at the end), so remove any copy the model wrote.
    text = text.replace(prompt.ONBOARD_INVITE, " ")
    invite_parts = set(split_sentences(prompt.ONBOARD_INVITE))
    sentences = [s for s in split_sentences(text) if s not in invite_parts]
    if cta:
        # The invite is two short sentences, so one sentence of answer fits before it.
        sentences = sentences[: max(1, MAX_SENTENCES - len(invite_parts))] + [prompt.ONBOARD_INVITE]
    else:
        sentences = sentences[:MAX_SENTENCES]
    clean: list[str] = []
    for item in suggestions or []:
        if not isinstance(item, str):
            continue
        item = _plain(item)[:SUGGESTION_MAX_CHARS].strip()
        if item and not has_price(item) and item.lower() not in {c.lower() for c in clean}:
            clean.append(item)
        if len(clean) == MAX_SUGGESTIONS:
            break
    return " ".join(sentences), clean


# ---- chat ------------------------------------------------------------------------------


def _clean_page(page: str | None) -> str | None:
    if not page:
        return None
    page = page.strip()
    return page if re.fullmatch(r"/[A-Za-z0-9/_\-.]{0,120}", page) else None


def _model_reply(body: SalesChatIn) -> dict | None:
    """{reply, suggestions, cta} from the model, or None to use the rules."""
    if ai_service.select_provider() != "gemini":
        return None
    if MODEL_BUDGET.hit("all"):
        log.info("sales.chat.model_budget_exhausted")
        return None
    history = [t.model_dump() for t in body.history]
    messages = prompt.build_messages(body.message, history, _clean_page(body.page))
    try:
        data = ai_service.llm_json(messages, prompt.RESPONSE_SCHEMA, "sales_reply")
    except ai_service.ProviderError as exc:
        log.warning("sales.chat.model_failed reason=%s", exc)
        return None
    except Exception as exc:  # noqa: BLE001  (the sales chat must never break)
        log.warning("sales.chat.model_failed reason=%s", type(exc).__name__)
        return None
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        log.warning("sales.chat.model_failed reason=empty_reply")
        return None
    suggestions = data.get("suggestions")
    return {
        "reply": reply,
        "suggestions": suggestions if isinstance(suggestions, list) else [],
        "cta": data.get("cta") == "onboard",
    }


@router.post("/chat", response_model=SalesChatOut, dependencies=[Depends(limit_sales_chat)])
def sales_chat(body: SalesChatIn):
    try:
        model = _model_reply(body)
    except Exception as exc:  # noqa: BLE001
        log.warning("sales.chat.model_failed reason=%s", type(exc).__name__)
        model = None

    if model is not None:
        provider = "gemini"
        medical = rules.match_topic(body.message)
        is_medical = medical is not None and medical.name == "medical_advice"
        cta = (model["cta"] or rules.detect_cta(body.message)) and not is_medical
        reply, suggestions = finalize(model["reply"], model["suggestions"], cta)
        if not reply:
            model = None
    if model is None:
        provider = "rules"
        fallback = rules.rules_reply(body.message)
        cta = fallback["cta"] == "onboard"
        reply, suggestions = finalize(fallback["reply"], fallback["suggestions"], cta)

    log.info("sales.chat provider=%s cta=%s history=%d", provider, bool(cta), len(body.history))
    return SalesChatOut(reply=reply, suggestions=suggestions, cta="onboard" if cta else None, provider=provider)


# ---- leads -----------------------------------------------------------------------------


def _lead_from(body: SalesLeadIn) -> SalesLead:
    transcript = None
    if body.transcript:
        transcript = [{"role": t.role, "content": t.content.strip()} for t in body.transcript[-TRANSCRIPT_KEEP:]]
    return SalesLead(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        session_id=body.session_id,
        hospital=body.hospital,
        contact_name=body.contact_name,
        role=body.role,
        work_email=body.work_email,
        phone=body.phone,
        discharges_per_month=body.discharges_per_month,
        ehr=body.ehr,
        service_lines=body.service_lines,
        timeline=body.timeline,
        notes=body.notes,
        source_page=_clean_page(body.page),
        transcript=transcript,
    )


def _created(lead: SalesLead, email: emailer.RenderedEmail) -> dict:
    return SalesLeadCreated(
        id=lead.id, status="stored", email={"to": email.to, "subject": email.subject, "body": email.body}
    ).model_dump(mode="json")


@router.post(
    "/leads",
    response_model=SalesLeadCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_sales_leads)],
)
def create_lead(body: SalesLeadIn, db: Session = Depends(get_db)):
    lead = _lead_from(body)
    if body.website:
        # Honeypot filled in: look the same to the sender, store nothing.
        log.info("sales.lead.honeypot")
        return JSONResponse(_created(lead, emailer.render(lead)), status_code=status.HTTP_200_OK)

    db.add(lead)
    db.flush()
    _, email = emailer.store(db, lead)
    db.commit()
    log.info("sales.lead.stored transcript_turns=%d", len(lead.transcript or []))
    return _created(lead, email)


@router.get("/leads", response_model=list[SalesLeadOut])
def list_leads(db: Session = Depends(get_db), user: User = Depends(require_clinician)):
    leads = db.scalars(
        select(SalesLead).order_by(SalesLead.created_at.desc()).limit(LEADS_LIST_LIMIT)
    ).all()
    subjects: dict[uuid.UUID, str] = {}
    if leads:
        rows = db.execute(
            select(SalesEmail.lead_id, SalesEmail.subject)
            .where(SalesEmail.lead_id.in_([lead.id for lead in leads]))
            .order_by(SalesEmail.created_at)
        ).all()
        subjects = {lead_id: subject for lead_id, subject in rows}
    out = []
    for lead in leads:
        item = SalesLeadOut.model_validate(lead)
        item.email_subject = subjects.get(lead.id)
        out.append(item)
    return out
