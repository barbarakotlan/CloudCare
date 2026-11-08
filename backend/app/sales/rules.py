"""Keyword answers for the sales chat when the language model is unavailable.

Every answer is drawn from docs/product-brief.md and keeps the persona rules: first person
as Barbara's AI twin, at most three sentences, no price, no medical advice, honest caveats.
`detect_cta()` is also used on the model path, so buying intent is caught either way.
"""

import re
from dataclasses import dataclass, field

from app.sales.prompt import ONBOARDING_EMAIL, PRICING_RULE, SUPPORT_EMAIL


@dataclass(frozen=True)
class Topic:
    name: str
    patterns: tuple[str, ...]
    reply: str
    suggestions: tuple[str, ...] = field(default_factory=tuple)


def _rx(*words: str) -> tuple[str, ...]:
    return tuple(words)


# Order breaks ties: earlier topics win when two match equally well.
TOPICS: tuple[Topic, ...] = (
    Topic(
        "medical_advice",
        _rx(r"\bi(?:'m| am)? (?:have|having|feel|feeling|got)\b.*\b(pain|fever|bleed\w*|swell\w*|nause\w*|dizzy|symptoms?|sick)\b",
            r"\bmy (pain|wound|incision|fever|symptoms?|knee|hip|leg|chest|stitches|medicine|medication|dose|surgery)\b",
            r"\b(should|can) i (take|stop|skip|double)\b"),
        "I can't give medical advice, and if this is an emergency please call 911 now. "
        "For questions about your own recovery, your surgeon's office is the right place to ask. "
        "I'm happy to explain how CloudCare helps care teams with exactly these moments.",
        ("How does Foggy handle red flags?", "What is CloudCare?"),
    ),
    Topic(
        "identity",
        _rx(r"\b(are|r) (you|u) (a |an )?(real|human|person|bot|robot|ai|machine)\b",
            r"\b(real|actual) (person|human|barbara)\b", r"\bis this (a )?(bot|ai|human|real)\b",
            r"\bai twin\b", r"\btalking to (a )?(bot|human|person|ai)\b"),
        "I'm Barbara's AI twin, not Barbara herself, and a person on our team follows up on every request. "
        "I can answer questions about CloudCare in the meantime. What would you like to know?",
        ("What is CloudCare?", "Who is on the team?"),
    ),
    Topic(
        "pricing",
        _rx(r"\bpric(e|es|ed|ing)\b", r"\bcosts?\b", r"\bhow much\b", r"\bfees?\b", r"\bbudget\b",
            r"\bquote\b", r"\bexpensive\b", r"\bsubscription\b", r"\blicen[cs](e|ing)\b", r"\bpay\b"),
        f"We don't publish a price: {PRICING_RULE[0].lower()}{PRICING_RULE[1:-1]}, "
        f"and you can also email {ONBOARDING_EMAIL}.",
        ("What does a pilot look like?", "Does it work with Epic?"),
    ),
    Topic(
        "pilot",
        _rx(r"\bpilot", r"\bonboard", r"\bsign(?:ing)?[ -]?up\b", r"\bget(?:ting)? started\b",
            r"\btrial\b", r"\broll ?out\b", r"\bimplement\w*\b", r"\bset (?:it |this |us )?up\b",
            r"\bnext steps?\b", r"\bdeploy\w*\b"),
        "We're looking for pilot hospitals, and a person on our team scopes each pilot with you, including which "
        f"patients take part and who reviews alerts (you can also email {ONBOARDING_EMAIL}).",
        ("What does it cost?", "Is it HIPAA compliant?"),
    ),
    Topic(
        "contact",
        _rx(r"\bcontact\b", r"\be-?mail\b", r"\breach (you|someone|the team|your team)\b",
            r"\b(talk|speak) (to|with) (sales|someone|a person|a human|your team|the team)\b",
            r"\bget in touch\b"),
        f"You can email {ONBOARDING_EMAIL} about pilots and onboarding, or {SUPPORT_EMAIL} for help with an "
        "account, and a person on our team replies. Or leave your details here and we'll follow up.",
        ("What does a pilot look like?", "What is CloudCare?"),
    ),
    Topic(
        "hipaa",
        _rx(r"\bhipaa\b", r"\bbaas?\b", r"\bbusiness associate\b", r"\bcomplian\w*\b", r"\bphi\b",
            r"\bfda\b", r"\bregulat\w*\b", r"\bsoc ?2\b", r"\bcertif\w*\b", r"\bmedical device\b"),
        "To be straight with you: CloudCare isn't operating under HIPAA yet, we have no BAAs with our vendors, "
        "and it hasn't been reviewed by the FDA. Real patient data would first need HIPAA-eligible vendor plans "
        "and signed BAAs, which is part of scoping a pilot. Want to hear how a pilot would work?",
        ("What does a pilot look like?", "How is data secured?"),
    ),
    Topic(
        "epic",
        _rx(r"\bepic\b", r"\bmychart\b", r"\behr\b", r"\bemr\b", r"\bfhir\b", r"\bintegrat\w*\b",
            r"\bcerner\b", r"\boracle health\b", r"\bmeditech\b", r"\bhealth records?\b"),
        "Patients can connect Epic MyChart through SMART on FHIR to bring in medications, labs, visits and notes, "
        "read-only, and we flag MyChart medications that don't match the care plan. "
        "Today that runs against Epic's sandbox with test patients only, and clinician-side EHR workflows aren't built yet. "
        "Which EHR does your hospital use?",
        ("Is it HIPAA compliant?", "What does a pilot look like?"),
    ),
    Topic(
        "security",
        _rx(r"\bsecur\w*\b", r"\bencrypt\w*\b", r"\bprivacy\b", r"\bprivate\b", r"\bbreach\w*\b",
            r"\bhost(ed|ing)?\b", r"\bwhere (is|does) (the )?data\b", r"\bdata (stor\w*|protect\w*)\b",
            r"\baccess control\b"),
        "Data sits in a Supabase Postgres database with row-level security, the API runs on Render, and clinicians "
        "only see the patients assigned to them. MyChart tokens are encrypted and never reach the browser, and phone "
        "actions only go to the patient's own number. We're not operating under HIPAA yet, so a pilot starts with the vendor agreements.",
        ("Is it HIPAA compliant?", "How does Epic work?"),
    ),
    Topic(
        "voice",
        _rx(r"\bvoice\b", r"\bcalls?\b", r"\bcalling\b", r"\bphones?\b", r"\btalk\w*\b", r"\bspeak\w*\b",
            r"\bsms\b", r"\btexts?\b", r"\btexting\b"),
        "Patients can text Foggy in the app, talk to it in the browser, or press \"Call me\" for an automated "
        "check-in call from our toll-free number, and every channel follows the same rules. "
        "Check-in texts are built but stay off until carrier verification of the number finishes. "
        "You can hear a sample call on our home page.",
        ("Can I try a demo?", "How do check-ins work?"),
    ),
    Topic(
        "safety",
        _rx(r"\bemergenc\w*\b", r"\b911\b", r"\bred flags?\b", r"\bsafe(ty)?\b", r"\bhallucinat\w*\b",
            r"\bwrong answers?\b", r"\bmistakes?\b", r"\baccura\w*\b", r"\bguardrails?\b", r"\bliabilit\w*\b"),
        "Chest pain, trouble breathing, heavy bleeding or fainting are caught by fixed rules before any language "
        "model runs, and the reply always starts with \"Call 911 now.\" Foggy is designed to answer only from the "
        "clinician's care plan, never changes a dose, and only messages the care team when the patient says yes.",
        ("What do clinicians see?", "Can I try a demo?"),
    ),
    Topic(
        "checkins",
        _rx(r"\bcheck[ -]?ins?\b", r"\bsymptoms?\b", r"\breminders?\b", r"\bmedications?\b", r"\bdoses?\b",
            r"\bfollow[ -]?ups?\b"),
        "Foggy runs check-ins one question at a time: pain, symptoms like fever, wound changes, numbness or falls, "
        "and one question for each medicine dose due that day. The care team sees the result, and high-risk "
        "check-ins open an alert in their queue.",
        ("What do clinicians see?", "How does Foggy handle red flags?"),
    ),
    Topic(
        "clinicians",
        _rx(r"\bdashboard\b", r"\bworklist\b", r"\bclinicians?\b", r"\bnurs(e|es|ing)\b", r"\bqueue\b",
            r"\balerts?\b", r"\bescalat\w*\b", r"\btriage\b", r"\bsurgeons?\b", r"\banesthesi\w*\b",
            r"\bworkload\b", r"\bstaff\b"),
        "Clinicians get an urgency-first worklist: open emergencies first, then high alerts, with an explainable "
        "risk estimate shown separately. They acknowledge and resolve each alert with notes, and the dashboard "
        "records who reviewed it and when. Want to see it with the demo clinician account?",
        ("Can I try a demo?", "How do care plans get in?"),
    ),
    Topic(
        "care_plan",
        _rx(r"\bcare plans?\b", r"\bdischarge instructions?\b", r"\binstructions?\b", r"\bupload\w*\b",
            r"\bcontent\b", r"\btemplates?\b"),
        "Clinicians paste discharge instructions as text, the plan splits into sections, and Foggy uses it right away. "
        "Text answers show the section they came from, and if the plan doesn't cover a question Foggy says so instead of guessing.",
        ("How does Foggy stay safe?", "What does a pilot look like?"),
    ),
    Topic(
        "risk_model",
        _rx(r"\brisk\b", r"\bmachine learning\b", r"\bml\b", r"\bxgboost\b", r"\bpredict\w*\b",
            r"\bscor(e|es|ing)\b", r"\bmodel\b", r"\banalytics\b"),
        "Each check-in gets a risk estimate from an XGBoost model that shows its top three reasons, like fever or "
        "wound drainage. It's experimental and trained on synthetic data, so it would need validation on real "
        "outcomes, and the worklist always ranks open alerts above it.",
        ("What do clinicians see?", "What does a pilot look like?"),
    ),
    Topic(
        "evidence",
        _rx(r"\bcustomers?\b", r"\bclients?\b", r"\boutcomes?\b", r"\bresults?\b", r"\bevidence\b",
            r"\bstud(y|ies)\b", r"\broi\b", r"\breadmission\w*\b", r"\bwho (uses|is using)\b",
            r"\breferences?\b", r"\bcase stud\w*\b"),
        "Honestly, we're early: CloudCare has a working demo but no hospital customers yet and no published outcomes. "
        "That's exactly why we're looking for pilot hospitals to measure it with us.",
        ("What does a pilot look like?", "Can I try a demo?"),
    ),
    Topic(
        "llm",
        _rx(r"\bgemini\b", r"\bllm\b", r"gpt\b",r"\blanguage model\b", r"\bwhich ai\b",
            r"\bwhat ai\b", r"\bai model\b"),
        "Foggy uses Google Gemini to understand and phrase messages, while code decides what happens and "
        "emergencies use fixed wording. Today the text assistant runs on Gemini's free tier, which isn't suitable "
        "for real health information, so it would move to a paid tier with Google's data terms before a real pilot.",
        ("Is it HIPAA compliant?", "How does Foggy stay safe?"),
    ),
    Topic(
        "team",
        _rx(r"\bteam\b", r"\bfound(er|ers|ed)\b", r"\bco-?founders?\b", r"\bwho (built|made|are you|is behind)\b",
            r"\bbarbara\b", r"\bjacob\b", r"\banna\b", r"\bcompany\b", r"\bbackground\b"),
        "We're three co-founders: I'm Barbara Kotlan and I build the backend and data, Jacob Foti is our business "
        "lead, and Anna Kotlan leads AI and ML. You're chatting with my AI twin, and a person on the team follows up on every request.",
        ("What is CloudCare?", "What does a pilot look like?"),
    ),
    Topic(
        "demo",
        _rx(r"\bdemos?\b", r"\btry\b", r"\bsee it\b", r"\bshow me\b", r"\bwalk ?through\b", r"\btest (it|drive)\b",
            r"\bscreenshots?\b", r"\bvideo\b"),
        "You can text a demo Foggy and hear a sample call right on cloudcare.icu. To see both sides, sign in as "
        "patient@demo.com or clinician@demo.com with the password demo123; those accounts are public, so no real health information please.",
        ("What do clinicians see?", "What does a pilot look like?"),
    ),
    Topic(
        "timeline",
        _rx(r"\bhow long\b", r"\btimeline\b", r"\bhow (fast|quickly)\b", r"\bweeks?\b", r"\bmonths?\b", r"\bwhen can\b"),
        "Loading a care plan takes minutes and patients sign up on their own, but a real pilot also needs the vendor "
        "agreements and an agreed alert-review process. A person on our team scopes the timeline with you.",
        ("What does a pilot look like?", "Is it HIPAA compliant?"),
    ),
    Topic(
        "overview",
        _rx(r"\bwhat is\b", r"\bwhat's cloudcare\b", r"\bwhat do(es)? (you|it|cloudcare) do\b", r"\bhow does (it|cloudcare) work\b",
            r"\boverview\b", r"\bexplain\b", r"\btell me (more|about)\b", r"\bfoggy\b", r"\bcloudcare\b"),
        "CloudCare brings the care team's instructions home after surgery: patients get Foggy, a recovery assistant "
        "that answers from their clinician's own care plan by text, voice or phone, plus guided check-ins. "
        "Clinicians get an urgency-first worklist so they see who needs attention first. "
        "What does post-op follow-up look like at your hospital today?",
        ("How does Foggy stay safe?", "Does it work with Epic?", "What does a pilot look like?"),
    ),
    Topic(
        "greeting",
        _rx(r"^\s*(hi|hello|hey|hiya|good (morning|afternoon|evening)|greetings)\b"),
        "Hi, I'm Barbara's AI twin, co-founder of CloudCare. We help surgical and anesthesia teams keep patients "
        "on track after discharge with Foggy, a recovery assistant that answers from the clinician's own care plan. "
        "What brings you here today?",
        ("What is CloudCare?", "What does a pilot look like?", "Can I try a demo?"),
    ),
    Topic(
        "thanks",
        _rx(r"^\s*(thanks|thank you|thx|great|cool|ok(ay)?|got it|perfect|awesome)\b"),
        "Glad to help. If you'd like to see whether CloudCare fits your team, I can get your hospital set up for a "
        "pilot conversation, or you can try the demo on cloudcare.icu.",
        ("What does a pilot look like?", "Can I try a demo?"),
    ),
)

DEFAULT_REPLY = (
    "Good question, and I don't want to guess. Someone on our team can follow up if you email "
    f"{ONBOARDING_EMAIL}, or I can tell you how Foggy works, how Epic MyChart fits in, or what a pilot looks like."
)
DEFAULT_SUGGESTIONS = ("What is CloudCare?", "Does it work with Epic?", "What does a pilot look like?")

_COMPILED = tuple((t, tuple(re.compile(p, re.IGNORECASE) for p in t.patterns)) for t in TOPICS)

# Buying intent: pilot, pricing, onboarding, sign up, a demo for their own organisation.
_CTA = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bpilot", r"\bonboard", r"\bsign(?:ing)?[ -]?up\b", r"\bget(?:ting)? started\b",
    r"\bpric(e|es|ing)\b", r"\bcosts?\b", r"\bhow much\b", r"\bquote\b", r"\bcontract\b",
    r"\bpurchase\b", r"\bbuy(ing)?\b", r"\btrial\b", r"\bset (?:it |this |us |cloudcare )?up\b",
    r"\b(use|try|deploy|roll out|bring|implement|adopt)\b.*\b(it|this|cloudcare)\b.*\b(at|in|for) (my|our)\b",
    r"\bdemo\b.*\b(my|our)\b.*\b(hospital|team|clinic|health system|department|unit|practice|group|surgeons?|nurses?|staff)\b",
    r"\b(talk|speak) (to|with) (sales|someone|a person|a human|your team)\b",
    r"\bnext steps?\b", r"\bready\b", r"\binterested\b",
))
_NOT_NOW = re.compile(
    r"\b(not|isn't|aren't) (interested|ready|looking)\b|\bno thanks\b|\bjust (looking|browsing|curious)\b",
    re.IGNORECASE,
)


def detect_cta(message: str) -> bool:
    text = message or ""
    if _NOT_NOW.search(text):
        return False
    return any(p.search(text) for p in _CTA)


def match_topic(message: str) -> Topic | None:
    best: Topic | None = None
    best_hits = 0
    for topic, patterns in _COMPILED:
        hits = sum(1 for p in patterns if p.search(message))
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


def rules_reply(message: str) -> dict:
    """{reply, suggestions, cta} from keywords. Never raises."""
    topic = match_topic(message or "")
    cta = detect_cta(message)
    if topic is None:
        reply, suggestions = DEFAULT_REPLY, list(DEFAULT_SUGGESTIONS)
    else:
        reply, suggestions = topic.reply, list(topic.suggestions)
        if topic.name == "medical_advice":
            cta = False  # a patient asking about their own symptoms is not a sales lead
    return {"reply": reply, "suggestions": suggestions[:3], "cta": "onboard" if cta else None,
            "topic": topic.name if topic else "default"}
