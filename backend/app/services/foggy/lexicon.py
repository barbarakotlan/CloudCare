"""Word lists and small parsers Foggy's router uses without any language model.

These rules run on every message. They are the safety floor: emergency words, plan call
triggers, dose-change requests and check-in requests are recognized even when the model
is unavailable. Each hit records whether its own clause is a denial, a hypothetical, a
quotation or old history, so "no chest pain" or "what if I get chest pain?" is not
treated as a report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---- text helpers -------------------------------------------------------------------


def normalize(text: str) -> str:
    """Lowercase, straight quotes, single spaces."""
    text = (text or "").lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("°", " degrees ")
    text = re.sub(r"\bnine[\s-]+one[\s-]+one\b", "911", text)
    text = re.sub(r"\b9[\s-]1[\s-]1\b", "911", text)
    return re.sub(r"\s+", " ", text).strip()


def _rx(*patterns: str) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


# Clause boundaries: a negation or "if" only covers its own clause.
CLAUSE_BREAK = re.compile(r"[.!?;,:](?:\s|$)|\bbut\b|\band\b|\bthough\b|\bhowever\b|\byet\b|\balso\b")
NEGATION_WINDOW = 3  # words before a match that a negator must sit in ("no idea why my chest hurts" is a report)

NEGATORS = re.compile(
    r"\b(no|not|never|without|deny|denies|don't|dont|do not|doesn't|does not|didn't|did not|"
    r"haven't|have not|hasn't|has not|isn't|aren't|wasn't|weren't|none|nor|neither|free of|"
    r"no longer|zero)\b"
)
HYPOTHETICAL = re.compile(
    r"\b(if|what if|in case|when should|when do i|when would|should i ever|would|hypothetically|"
    r"suppose|supposing|let's say|imagine|what happens|how do i know|how would i know|"
    r"what does .{0,30}(say|mean)|what should i do|says|say|said|mentions|mentioned|example|"
    r"worried about getting|afraid of getting|risk of|signs of|warning signs?)\b"
)
OLD_HISTORY = re.compile(r"\b(years? ago|last year|as a (kid|child)|when i was (a|young)|in the past|history of|months ago)\b")


@dataclass
class Hit:
    kind: str
    start: int
    end: int
    negated: bool  # denial, hypothetical, quotation or old history in the same clause

    @property
    def reported(self) -> bool:
        return not self.negated


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    for m in CLAUSE_BREAK.finditer(text, 0, start):
        left = m.end()
    nxt = CLAUSE_BREAK.search(text, end)
    right = nxt.start() if nxt else len(text)
    return left, right


def _guarded(text: str, start: int, end: int, hypothetical_ok: bool = True) -> bool:
    left, right = _clause_bounds(text, start, end)
    before = text[left:start]
    clause = text[left:right]
    near = " ".join(before.split()[-NEGATION_WINDOW:])
    if NEGATORS.search(near):
        return True
    if hypothetical_ok and HYPOTHETICAL.search(before):
        return True
    return bool(OLD_HISTORY.search(clause))


def _find(groups: dict[str, list[re.Pattern]], text: str, guard: bool = True,
          hypothetical_ok: bool = True) -> list[Hit]:
    hits = []
    for kind, patterns in groups.items():
        for p in patterns:
            for m in p.finditer(text):
                negated = _guarded(text, m.start(), m.end(), hypothetical_ok) if guard else False
                hits.append(Hit(kind, m.start(), m.end(), negated))
    return hits


# ---- emergency (EMERGENCY_911) ------------------------------------------------------

EMERGENCY = {
    "chest_pain": _rx(
        r"\bchest (?:really |still |kind of |kinda |is |feels |started )?(?:pain|pains|pressure|tightness|"
        r"hurts|hurt|hurting|aches|aching|ache|tight|heavy|squeezing)\b",
        r"\bpains? in (?:my|the) chest\b",
        r"\bheart attack\b",
    ),
    "trouble_breathing": _rx(
        r"\b(?:can't|cant|cannot|can not|couldn't|could not|unable to)\s+(?:really\s+)?(?:breathe|breath|"
        r"catch my breath|get my breath|get a breath|get enough air|get air)\b",
        r"\b(?:trouble|difficulty|hard time|problems?|struggling|struggle|hard) (?:with )?(?:breathing|to breathe)\b",
        r"\bshort(?:ness)? of breath\b",
        r"\bout of breath\b",
        r"\bbreathless\b",
        r"\bgasping\b",
        r"\bbreathing (?:is |feels )?(?:hard|difficult|labored|laboured|weird|fast)\b",
    ),
    "heavy_bleeding": _rx(
        r"\bbleeding (?:really |very )?(?:heavily|a lot|badly|lots|everywhere|through)\b",
        r"\bheavy bleeding\b",
        r"\bbleeding (?:that )?(?:won't|will not|doesn't|does not|didn't) stop\b",
        r"\b(?:won't|will not|can't|cannot) stop (?:the )?bleeding\b",
        r"\b(?:lots|a lot|tons) of blood\b",
        r"\bblood (?:is )?(?:pouring|gushing|everywhere|soaking|spurting)\b",
        r"\bsoak(?:ed|ing)? (?:through )?(?:with|in) blood\b",
        r"\bbleeding heavy\b",
    ),
    "fainting": _rx(
        r"\b(?:fainted|fainting|faint(?:ed)? earlier|passed out|pass out|passing out|blacked out|black out|"
        r"blacking out|lost consciousness|losing consciousness|unconscious|collapsed)\b",
    ),
    "call_911": _rx(
        r"\b(?:call|calling|dial|phone) (?:911|an ambulance|the ambulance|emergency services)\b",
        r"\bneed an ambulance\b",
    ),
    "self_harm": _rx(r"\b(?:suicidal|kill myself|end my life|want to die|hurt myself)\b"),
}
EMERGENCY_SIGNS = ("chest_pain", "trouble_breathing", "heavy_bleeding", "fainting", "call_911", "self_harm")


def emergency_hits(text: str) -> list[Hit]:
    t = normalize(text)
    hits = []
    for h in _find(EMERGENCY, t):
        if h.kind == "call_911":
            # "Should I call 911?" counts as a request; only "when/if" questions do not.
            left, _ = _clause_bounds(t, h.start, h.end)
            before = t[left:h.start]
            h.negated = bool(re.search(r"\b(when|if|what if|in case|says|said|say|for what)\b", before)
                             or NEGATORS.search(before))
        hits.append(h)
    return hits


# ---- plan call triggers (CALL_SURGEON) ------------------------------------------------

CALL_TRIGGERS = {
    "redness_drainage": _rx(
        r"\bredness\b.{0,25}?\b(?:spreading|worse|increasing|growing|bigger|getting)\b",
        r"\b(?:more|increasing|spreading|worse|worsening|new) (?:redness|drainage|pus|discharge)\b",
        r"\b(?:drainage|draining|pus|oozing|discharge|leaking)\b",
        r"\b(?:red|redder) and (?:spreading|hot|warm|swollen)\b",
    ),
    "calf_pain_swelling": _rx(
        r"\bcal(?:f|ves)\b.{0,40}?\b(?:pain|painful|hurts?|hurting|swollen|swelling|tender|sore|aching|aches|"
        r"warm|red|tight)\b",
        r"\b(?:pain|painful|swollen|swelling|tender|sore|aching|cramp)\b.{0,25}?\bcal(?:f|ves)\b",
    ),
    "uncontrolled_pain": _rx(
        r"\bpain\b.{0,30}?\b(?:out of control|uncontrolled|not controlled|isn't controlled|unbearable|"
        r"unmanageable|too much to handle)\b",
        r"\b(?:uncontrolled|unbearable|unmanageable|excruciating|out of control|out-of-control) pain\b",
        r"\b(?:medicine|meds|medication|medications|pills|oxycodone|acetaminophen|tylenol)\b.{0,25}?"
        r"\b(?:isn't|is not|aren't|are not|not|doesn't|don't) (?:helping|working|touching|controlling)\b",
        r"\bnothing (?:helps|is helping|works)\b",
        r"\bcan't (?:control|manage|handle) (?:the |my )?pain\b",
    ),
    "fall": _rx(
        r"\b(?:fell|fallen)\b(?!\s+asleep)",
        r"\b(?:had|took) a (?:bad |little |small )?fall\b",
        r"\b(?:tripped|slipped) and (?:fell|went down)\b",
    ),
    "numbness_tingling_color": _rx(
        r"\b(?:numb|numbness|tingling|tingly|tingles|pins and needles)\b",
        r"\b(?:turned|turning|looks?|look|is|are|gone|went)\s+(?:\w+\s+)?(?:blue|purple|pale|white|gray|grey|"
        r"black|dusky)\b",
        r"\b(?:different|changed?|change in|new|weird|strange) (?:skin )?colou?r\b",
        r"\bcolou?r (?:change|changed|is different|looks different|looks off)\b",
    ),
}
CALL_TRIGGER_KINDS = ("fever", *CALL_TRIGGERS.keys())
FEVER_LIMIT_F = 101.5  # plan trigger: strictly over this


def call_trigger_hits(text: str) -> list[Hit]:
    return _find(CALL_TRIGGERS, normalize(text))


_TEMP_PATTERNS = (
    re.compile(r"(\d{2,3}(?:\.\d+)?)\s*(?:degrees|degree|deg\b)\s*(c|celsius|f|fahrenheit)?"),
    re.compile(r"(\d{2,3}(?:\.\d+)?)\s*(f|c)\b"),
    re.compile(r"\b(?:temp|temperature|fever)\b[^0-9]{0,25}?(\d{2,3}(?:\.\d+)?)\s*(c|celsius|f|fahrenheit)?"),
)


def parse_temperature(text: str) -> float | None:
    """Temperature in Fahrenheit if the message states one (Celsius converted)."""
    t = normalize(text)
    for p in _TEMP_PATTERNS:
        m = p.search(t)
        if not m:
            continue
        value = float(m.group(1))
        unit = (m.group(2) or "").lower() if m.lastindex and m.lastindex >= 2 else ""
        if unit.startswith("c") or (not unit and 34 <= value <= 43):
            value = value * 9 / 5 + 32
        if 90 <= value <= 110:
            return round(value, 1)
    return None


def fever_reported(text: str) -> tuple[bool, float | None]:
    """(reported, temperature). A stated temperature in a denial/hypothetical clause does not count."""
    t = normalize(text)
    temp = parse_temperature(t)
    if temp is None:
        return False, None
    m = re.search(r"\d{2,3}(?:\.\d+)?", t)
    if m and _guarded(t, m.start(), m.end()):
        return False, temp
    return True, temp


# ---- dose changes (REFUSE_DOSE_CHANGE) ------------------------------------------------

MED_WORDS = re.compile(
    r"\b(acetaminophen|tylenol|paracetamol|oxycodone|oxy|percocet|aspirin|dose|doses|dosage|pill|pills|"
    r"tablet|tablets|medicine|medicines|medication|medications|meds|mg|milligrams?|painkillers?)\b"
)
DOSE_CHANGE = re.compile(
    r"\b(double|doubling|twice as much|triple|extra|more than|an extra|another (?:dose|pill|tablet)|"
    r"increase|increasing|raise|bump up|decrease|decreasing|lower|lowering|reduce|reducing|cut (?:back|down)|"
    r"half|halve|split|less than|instead of|switch|swap|replace|stop taking|stop my|stop the|stopping|"
    r"quit|quitting|go off|come off|get off|skip|skipping|change (?:my|the) (?:dose|dosage|medicine|medication|"
    r"schedule|timing)|reschedule|more often|less often|take more|take less|higher dose|lower dose|"
    r"two (?:pills|tablets|doses))\b"
)
STOP_WORDS = re.compile(r"\b(stop|stopping|quit|quitting|go off|come off|get off)\b")


def dose_change_requested(text: str) -> bool:
    t = normalize(text)
    return bool(MED_WORDS.search(t) and DOSE_CHANGE.search(t))


def is_stop_request(text: str) -> bool:
    return bool(STOP_WORDS.search(normalize(text)))


# ---- check-in (START_CHECKIN) ----------------------------------------------------------

CHECKIN_START = _rx(
    r"\bcheck[- ]?in\b",
    r"\b(?:feel|feeling|feels|felt) (?:a bit |a little |kind of |kinda |really |just |so )?"
    r"(?:off|weird|strange|funny|wrong|not right|not myself|unwell|sick|awful|terrible|worse|lousy|crummy|bad|"
    r"icky|blah)\b",
    r"\bsomething (?:feels|is|seems) (?:off|wrong|not right|weird)\b",
    r"\bnot feeling (?:well|right|good|great|myself)\b",
    r"\bdon't feel (?:well|right|good|great)\b",
)


def checkin_requested(text: str) -> bool:
    t = normalize(text)
    return any(p.search(t) for p in CHECKIN_START)


CHECKIN_CANCEL = re.compile(r"^(?:stop|cancel|quit|later|not now|stop the check[- ]?in|cancel the check[- ]?in|"
                            r"let's do this later|maybe later|never mind|nevermind)[.!]*$")


# ---- out of scope (NOT_IN_PLAN) ------------------------------------------------------

OUT_OF_SCOPE = {
    "missed_dose": _rx(
        r"\b(?:missed|forgot|forget|forgotten|skipped|didn't take)\b.{0,30}?\b(?:dose|doses|pill|pills|aspirin|"
        r"acetaminophen|tylenol|oxycodone|medicine|medication|meds)\b",
        r"\bmissed (?:a |my |the )?dose\b",
    ),
    "dose_interval_or_max": _rx(
        r"\b(?:how many hours|how long|how often|between|maximum|max|most|limit|how many|per day|a day|daily)\b"
        r".{0,40}?\b(?:oxycodone|oxy|percocet)\b",
        r"\b(?:oxycodone|oxy|percocet)\b.{0,40}?\b(?:how many hours|how often|between doses|maximum|max|limit|"
        r"how many|per day|a day)\b",
    ),
    "unlisted_medication": _rx(
        r"\b(?:ibuprofen|advil|motrin|aleve|naproxen|benadryl|melatonin|nyquil|tramadol|vitamins?|supplements?|"
        r"antibiotics?|sleeping pills?|cbd|herbal|zinc|turmeric|gabapentin|celebrex|tums|antacids?|laxatives?|"
        r"stool softeners?|ambien|xanax|valium|codeine|hydrocodone|vicodin|morphine|excedrin)\b",
    ),
    "alcohol_or_cannabis": _rx(
        r"\b(?:wine|beer|beers|alcohol|liquor|vodka|whiskey|whisky|cocktails?|booze|cannabis|marijuana|weed|"
        r"edibles?|thc|pot|smoke|smoking|vape|vaping|cigarettes?)\b",
    ),
    "second_opinion": _rx(
        r"\b(?:wrong (?:treatment|surgery|choice|decision|procedure)|second opinion|botched|right treatment|"
        r"bad surgeon|good surgeon|surgeon (?:picked|chose|made|messed)|should i have (?:had|gotten))\b",
    ),
    "work_or_travel": _rx(
        r"\b(?:work|working|job|office|desk|shift|fly|flight|flying|plane|airplane|travel|traveling|travelling|"
        r"trip|vacation|road trip|abroad)\b",
    ),
    "non_medical": _rx(
        r"\b(?:joke|jokes|weather|game|score|sports|basketball|football|baseball|soccer|hockey|movie|movies|song|"
        r"recipe|news|stocks?|president|election|capital of|who won|tell me a story|poem|riddle)\b",
    ),
    "feelings": _rx(
        r"\b(?:scared|afraid|anxious|anxiety|worried|nervous|sad|depressed|lonely|overwhelmed|stressed|"
        r"frightened|upset|crying|hopeless)\b",
    ),
    "other_medical": _rx(
        r"\b(?:infected|infection|blood clot|clot|dvt|diagnose|diagnosis|is it normal|is this normal)\b",
    ),
}
FAMILY = re.compile(
    r"\bmy (sister|brother|mom|mother|dad|father|wife|husband|son|daughter|kid|child|friend|neighbou?r|"
    r"grandma|grandpa|grandmother|grandfather|aunt|uncle|cousin|partner|roommate|boyfriend|girlfriend)\b"
)
THIRD_PERSON = re.compile(r"\b(she|he|her|his|him|they|them|their)\b")


def out_of_scope_kind(text: str) -> tuple[str | None, str]:
    """(kind, matched words) for the first out-of-scope rule that matches, else (None, '')."""
    t = normalize(text)
    fam = FAMILY.search(t)
    if fam and THIRD_PERSON.search(t):
        return "family_member", fam.group(1)
    for kind, patterns in OUT_OF_SCOPE.items():
        for p in patterns:
            m = p.search(t)
            if m:
                return kind, m.group(0)
    return None, ""


def family_relation(text: str) -> str | None:
    m = FAMILY.search(normalize(text))
    return m.group(1) if m else None


# ---- operational -----------------------------------------------------------------------

IDENTITY = _rx(
    r"\bare you (?:a |an |actually |really )?(?:real )?(?:doctor|nurse|human|person|real|robot|bot|ai|machine|"
    r"computer|medical professional|physician)\b",
    r"\bwho (?:are|is) (?:you|this|foggy)\b",
    r"\bwhat are you\b",
    r"\bam i (?:talking|texting|speaking) (?:to|with) (?:a |an )?(?:real|human|person|doctor|nurse|bot|ai|robot)\b",
)
CAPABILITY = _rx(
    r"\b(?:can|could|will|would) you (?:please )?(?:call|phone|text|email|message|contact|reach|notify|page|"
    r"tell|let)\b",
    r"^(?:please )?(?:call|text|message|contact|email|notify|page) (?:my |the )?(?:doctor|surgeon|nurse|"
    r"care team|medical team|team|clinic|dr)\b",
    r"\b(?:i want|i'd like|i would like|i need) (?:you )?to (?:talk|speak|message|contact|reach|call) "
    r"(?:to |with )?(?:my |a |the )?(?:doctor|surgeon|nurse|care team|medical team|team|someone|person|human)\b",
    r"\bwhat can you do\b",
    r"\bhow can you help\b",
)
GREETING = re.compile(r"^(?:hi|hello|hey|hiya|good (?:morning|afternoon|evening)|yo)\b[\s!,.a-z]{0,20}$")
THANKS = re.compile(r"^(?:ok(?:ay)?[, ]*)?(?:thanks|thank you|thx|ty|thanks so much|thank you so much)\b[\s!,.a-z]{0,25}$")
ACK = re.compile(r"^(?:ok|okay|got it|cool|great|alright|all right|sounds good|good|perfect|k)[.!]*$")


def asks_identity(text: str) -> bool:
    t = normalize(text)
    return any(p.search(t) for p in IDENTITY)


def asks_capability(text: str) -> bool:
    t = normalize(text)
    return any(p.search(t) for p in CAPABILITY)


def small_talk(text: str) -> str | None:
    t = normalize(text)
    if GREETING.match(t):
        return "greeting"
    if THANKS.match(t):
        return "thanks"
    if ACK.match(t):
        return "ack"
    return None


# ---- consent and check-in answers --------------------------------------------------------

_FILLER = re.compile(
    r"\b(please|thanks|thank you|go ahead|send it|send that|send the message|do it|do that|message my care team|"
    r"message them|message my team|message the team|contact them|contact my care team|that would be great|"
    r"that's fine|that is fine|for now|right now|i'm good|im good|i am good|i'm okay|i'm ok|i'm fine|"
    r"not now|no need|that's ok|that's okay)\b"
)
YES_WORDS = {"yes", "yeah", "yep", "yup", "ya", "yea", "sure", "ok", "okay", "please", "alright", "definitely",
             "absolutely", "correct", "affirmative", "y", "of course", "i do", "i did", "i have", "go ahead", "do it",
             "send it", "please do", "sounds good"}
NO_WORDS = {"no", "nope", "nah", "n", "not now", "never mind", "nevermind", "don't", "dont", "do not",
            "no need", "i'm good", "im good", "no thanks", "no thank you", "i didn't", "i haven't", "none",
            "nothing", "not at all", "negative"}
UNCLEAR_WORDS = {"maybe", "i don't know", "i dont know", "not sure", "idk", "hmm", "um", "uh", "i guess",
                 "perhaps", "dunno", "possibly", "kind of", "sort of", "i think so", "what", "huh"}


def _strip(text: str) -> str:
    return re.sub(r"[^a-z0-9' ]+", " ", normalize(text)).strip()


def yes_no(text: str) -> str | None:
    """'yes' | 'no' | 'unclear' for a short reply, None when the message says more than that."""
    t = _strip(text)
    if not t:
        return None
    if t in YES_WORDS or t in NO_WORDS or t in UNCLEAR_WORDS:
        return "yes" if t in YES_WORDS else "no" if t in NO_WORDS else "unclear"
    first = t.split()[0]
    two = " ".join(t.split()[:2])
    three = " ".join(t.split()[:3])
    rest = _FILLER.sub(" ", t)
    lead = None
    for cand in (three, two, first):
        if cand in NO_WORDS:
            lead = "no"
            rest = rest.replace(cand, " ", 1) if rest.startswith(cand) else rest
            break
        if cand in YES_WORDS:
            lead = "yes"
            rest = rest.replace(cand, " ", 1) if rest.startswith(cand) else rest
            break
        if cand in UNCLEAR_WORDS:
            lead = "unclear"
            rest = rest.replace(cand, " ", 1) if rest.startswith(cand) else rest
            break
    if lead is None:
        return None
    leftover = [w for w in rest.split() if w not in YES_WORDS and w not in NO_WORDS and w not in {
        "a", "the", "to", "my", "me", "it", "that", "i", "you", "and", "so", "just", "then", "now", "thank",
        "thanks", "team", "care", "please", "message", "send", "them", "sure", "of", "course", "really", "is", "fine",
    }]
    return lead if not leftover else None


_NUM_WORDS = {"zero": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10}


def parse_pain(text: str, bare_ok: bool) -> int | None:
    """Pain score 0-10. bare_ok: the message answers "what is your pain level", so a lone number counts."""
    t = normalize(text)
    m = re.search(r"\b(\d{1,2})\s*(?:/|out of)\s*10\b", t)
    if m and int(m.group(1)) <= 10:
        return int(m.group(1))
    m = re.search(r"\bpain\b[^.?!]{0,25}?\b(\d{1,2}|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b", t)
    if m:
        v = _NUM_WORDS.get(m.group(1), None) if not m.group(1).isdigit() else int(m.group(1))
        if v is not None and v <= 10:
            return v
    if bare_ok:
        m = re.search(r"\b(\d{1,2}|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b", t)
        if m:
            v = _NUM_WORDS[m.group(1)] if not m.group(1).isdigit() else int(m.group(1))
            if v <= 10:
                return v
    return None


MEDS_YES = re.compile(r"\b(?:took|taken|been taking) (?:all )?(?:of )?(?:my|the|them|all|everything)\b|"
                      r"\b(?:taking|took|taken) (?:them|it|my \w+) as (?:prescribed|planned|directed|the plan says)\b|"
                      r"\bon schedule\b|\ball of them\b")
MEDS_NO = re.compile(r"\b(missed|forgot|skipped|didn't take|did not take|haven't taken|ran out)\b")
MEDS_UNCLEAR = re.compile(r"\b(some|most|mostly|i think|not sure|maybe|kind of|sort of|i guess|probably|"
                          r"don't remember|can't remember|almost)\b")


def parse_meds(text: str, bare_ok: bool) -> str | None:
    t = normalize(text)
    no, yes = MEDS_NO.search(t), MEDS_YES.search(t)
    if bare_ok and MEDS_UNCLEAR.search(t) and not no:
        return "unclear"  # "I think so" is not a yes
    if no:
        return "no"
    if yes:
        return "yes"
    if bare_ok:
        yn = yes_no(t)
        if yn:
            return yn
    return None


NUMB_DENY = re.compile(r"\bno (?:new )?(?:numbness|tingling|color change|colour change|change in colou?r)\b|"
                       r"\bnothing like that\b")
FALL_DENY = re.compile(r"\b(?:no falls?|haven't fallen|have not fallen|didn't fall|did not fall|no,? i didn't|"
                       r"not fallen|never fell)\b")


def parse_numbness(text: str, bare_ok: bool) -> str | None:
    t = normalize(text)
    if NUMB_DENY.search(t):
        return "no"
    hits = [h for h in call_trigger_hits(t) if h.kind == "numbness_tingling_color"]
    if any(h.reported for h in hits):
        return "yes"
    if hits:
        return "no"
    if bare_ok:
        yn = yes_no(t)
        if yn in ("yes", "no"):
            return yn
        if re.search(r"\b(a little|a bit|some|kind of)\b", t):
            return "yes"
    return None


def parse_fall(text: str, bare_ok: bool) -> str | None:
    t = normalize(text)
    if FALL_DENY.search(t):
        return "no"
    hits = [h for h in call_trigger_hits(t) if h.kind == "fall"]
    if any(h.reported for h in hits):
        return "yes"
    if hits:
        return "no"
    if bare_ok:
        yn = yes_no(t)
        if yn in ("yes", "no"):
            return yn
    return None
