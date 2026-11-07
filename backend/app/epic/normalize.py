"""Turns Epic FHIR resources (R4, and STU3 for labs) into the flat shapes the
dashboard renders. Every field is optional on Epic's side, so every accessor here
tolerates missing or oddly shaped data and returns None instead of raising.
"""

import base64
import binascii
import html
import re
from collections.abc import Callable
from html.parser import HTMLParser

PREVIEW_CHARS = 600
_FHIR_ID = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")


def is_fhir_id(value: str) -> bool:
    return bool(_FHIR_ID.match(value or ""))


# ---- small accessors -----------------------------------------------------------------


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def concept_text(concept) -> str | None:
    """CodeableConcept (or a list of them, or a bare Coding) -> display text."""
    concept = _first(concept)
    if not isinstance(concept, dict):
        return None
    if _str(concept.get("text")):
        return _str(concept["text"])
    # A bare Coding (R4 Encounter.class, for example).
    if "coding" not in concept:
        return _str(concept.get("display")) or _str(concept.get("code"))
    for coding in concept.get("coding") or []:
        if isinstance(coding, dict) and _str(coding.get("display")):
            return _str(coding["display"])
    for coding in concept.get("coding") or []:
        if isinstance(coding, dict) and _str(coding.get("code")):
            return _str(coding["code"])
    return None


def reference_display(ref) -> str | None:
    ref = _first(ref)
    return _str(ref.get("display")) if isinstance(ref, dict) else None


def _number(value) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{value:g}" if isinstance(value, float) else str(value)
    return _str(value)


def quantity_text(q) -> tuple[str | None, str | None]:
    """Quantity -> (value, unit)."""
    if not isinstance(q, dict):
        return None, None
    value = _number(q.get("value"))
    if value is not None and _str(q.get("comparator")):
        value = f"{q['comparator']}{value}"
    return value, _str(q.get("unit")) or _str(q.get("code"))


def _quantity_string(q) -> str | None:
    value, unit = quantity_text(q)
    if value is None:
        return None
    return f"{value} {unit}" if unit else value


def _period_start(period) -> str | None:
    return _str(period.get("start")) if isinstance(period, dict) else None


def _period_end(period) -> str | None:
    return _str(period.get("end")) if isinstance(period, dict) else None


# ---- medications (MedicationRequest R4, tolerant of STU3) ------------------------------------


_PERIOD_UNITS = {"s": "second", "min": "minute", "h": "hour", "d": "day", "wk": "week", "mo": "month", "a": "year"}


def _timing_text(timing) -> str | None:
    if not isinstance(timing, dict):
        return None
    coded = concept_text(timing.get("code"))
    if coded:
        return coded
    repeat = timing.get("repeat")
    if not isinstance(repeat, dict):
        return None
    freq = repeat.get("frequency")
    period = repeat.get("period")
    unit = _PERIOD_UNITS.get(str(repeat.get("periodUnit") or ""), _str(repeat.get("periodUnit")))
    if isinstance(freq, (int, float)) and isinstance(period, (int, float)) and unit:
        times = "once" if freq == 1 else ("twice" if freq == 2 else f"{_number(freq)} times")
        every = unit if period == 1 else f"{_number(period)} {unit}s"
        return f"{times} every {every}" if period != 1 else f"{times} a {unit}"
    when = repeat.get("when")
    if isinstance(when, list) and when:
        return ", ".join(str(w) for w in when)
    return None


def _dose_text(dosage: dict) -> str | None:
    # R4: dosage.doseAndRate[].doseQuantity / doseRange. STU3: dosage.doseQuantity.
    dose_and_rate = _first(dosage.get("doseAndRate"))
    candidates = []
    if isinstance(dose_and_rate, dict):
        candidates += [dose_and_rate.get("doseQuantity")]
        rng = dose_and_rate.get("doseRange")
        if isinstance(rng, dict):
            low, high = _quantity_string(rng.get("low")), _quantity_string(rng.get("high"))
            if low and high:
                return f"{low} to {high}"
    candidates += [dosage.get("doseQuantity")]
    for q in candidates:
        text = _quantity_string(q)
        if text:
            return text
    return None


def medication(resource: dict, resolve: Callable[[str], dict | None] | None = None) -> dict:
    name = concept_text(resource.get("medicationCodeableConcept"))
    med_ref = resource.get("medicationReference")
    if not name and isinstance(med_ref, dict):
        name = _str(med_ref.get("display"))
        reference = _str(med_ref.get("reference"))
        if not name and reference:
            if reference.startswith("#"):
                for contained in resource.get("contained") or []:
                    if isinstance(contained, dict) and contained.get("id") == reference[1:]:
                        name = concept_text(contained.get("code"))
            elif resolve:
                med = resolve(reference)
                if med:
                    name = concept_text(med.get("code"))

    dosage = _first(resource.get("dosageInstruction"))
    dose_text = frequency_text = None
    if isinstance(dosage, dict):
        frequency_text = _timing_text(dosage.get("timing"))
        # Epic usually fills dosage.text with the full sig ("Take 1 tablet by mouth
        # every 6 hours"); prefer it over a bare quantity.
        dose_text = _str(dosage.get("text")) or _dose_text(dosage) or _str(dosage.get("patientInstruction"))

    requester = resource.get("requester")
    if isinstance(requester, dict) and "agent" in requester:  # STU3: requester.agent
        requester = requester.get("agent")

    return {
        "name": name or "Unnamed medication",
        "dose_text": dose_text,
        "frequency_text": frequency_text,
        "status": _str(resource.get("status")),
        "authored_on": _str(resource.get("authoredOn")),
        "prescriber": reference_display(requester),
    }


# ---- labs (Observation, STU3 or R4) ----------------------------------------------------------


def _value_text(holder: dict) -> tuple[str | None, str | None]:
    """value[x] -> (value, unit). Same element names in STU3 and R4."""
    if "valueQuantity" in holder:
        return quantity_text(holder["valueQuantity"])
    if "valueCodeableConcept" in holder:
        return concept_text(holder["valueCodeableConcept"]), None
    if "valueString" in holder:
        return _str(holder["valueString"]), None
    if "valueBoolean" in holder and isinstance(holder["valueBoolean"], bool):
        return ("Yes" if holder["valueBoolean"] else "No"), None
    if "valueInteger" in holder:
        return _number(holder["valueInteger"]), None
    if "valueRange" in holder and isinstance(holder["valueRange"], dict):
        low, high = _quantity_string(holder["valueRange"].get("low")), _quantity_string(holder["valueRange"].get("high"))
        return (f"{low or '?'} to {high or '?'}" if (low or high) else None), None
    if "valueRatio" in holder and isinstance(holder["valueRatio"], dict):
        num = _quantity_string(holder["valueRatio"].get("numerator"))
        den = _quantity_string(holder["valueRatio"].get("denominator"))
        return (f"{num}/{den}" if num and den else None), None
    if "valueDateTime" in holder:
        return _str(holder["valueDateTime"]), None
    if "valueTime" in holder:
        return _str(holder["valueTime"]), None
    if "valuePeriod" in holder and isinstance(holder["valuePeriod"], dict):
        return _period_start(holder["valuePeriod"]), None
    absent = concept_text(holder.get("dataAbsentReason"))
    return (f"Not available ({absent})" if absent else None), None


def _range_text(ranges) -> str | None:
    rng = _first(ranges)
    if not isinstance(rng, dict):
        return None
    if _str(rng.get("text")):
        return _str(rng["text"])
    low, high = quantity_text(rng.get("low")), quantity_text(rng.get("high"))
    unit = high[1] or low[1]
    if low[0] and high[0]:
        return f"{low[0]}-{high[0]}" + (f" {unit}" if unit else "")
    if low[0]:
        return f">={low[0]}" + (f" {unit}" if unit else "")
    if high[0]:
        return f"<={high[0]}" + (f" {unit}" if unit else "")
    return None


def lab(resource: dict) -> dict:
    value, unit = _value_text(resource)
    components = [c for c in resource.get("component") or [] if isinstance(c, dict)]
    if value is None and components:
        # Panels such as blood pressure keep their numbers in components.
        parts = []
        for comp in components:
            v, u = _value_text(comp)
            if v is None:
                continue
            label = concept_text(comp.get("code")) or "Value"
            parts.append(f"{label}: {v}" + (f" {u}" if u else ""))
        value = "; ".join(parts) or None
        unit = None

    # STU3: interpretation is one CodeableConcept. R4: a list of them.
    interpretation = concept_text(resource.get("interpretation"))
    effective = (
        _str(resource.get("effectiveDateTime"))
        or _period_start(resource.get("effectivePeriod"))
        or _str(resource.get("effectiveInstant"))
        or _str(resource.get("issued"))
    )
    reference_range = _range_text(resource.get("referenceRange"))
    if reference_range is None and components:
        reference_range = _range_text(components[0].get("referenceRange"))

    return {
        "name": concept_text(resource.get("code")) or "Lab result",
        "value": value,
        "unit": unit,
        "reference_range": reference_range,
        "status": _str(resource.get("status")),
        "effective_at": effective,
        "interpretation": interpretation,
    }


# ---- encounters --------------------------------------------------------------------------------


def encounter(resource: dict) -> dict:
    period = resource.get("period")
    location = _first(resource.get("location"))
    location_name = reference_display(location.get("location")) if isinstance(location, dict) else None
    # R4: reasonCode (CodeableConcept[]). STU3: reason (CodeableConcept[]).
    reason = concept_text(resource.get("reasonCode")) or concept_text(resource.get("reason"))
    return {
        "type": concept_text(resource.get("type")) or concept_text(resource.get("serviceType")),
        "class": concept_text(resource.get("class")),
        "start": _period_start(period),
        "end": _period_end(period),
        "location": location_name or reference_display(resource.get("serviceProvider")),
        "reason": reason,
    }


# ---- clinical notes (DocumentReference) ----------------------------------------------------------


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def note_plain_text(raw: str, content_type: str) -> str:
    """HTML or plain text -> tidy plain text. Markup never reaches the browser."""
    if content_type == "text/html":
        parser = _TextExtractor()
        parser.feed(raw)
        parser.close()
        text = "".join(parser.parts)
    else:
        text = html.unescape(raw) if "&" in raw and ";" in raw else raw
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.replace("\r", "").split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def decode_base64(data: str) -> str | None:
    try:
        return base64.b64decode(data, validate=False).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return None


def note_date(resource: dict) -> str | None:
    # R4: date. STU3: indexed (+ created). Both: context.period.start.
    context = resource.get("context")
    context = context if isinstance(context, dict) else {}
    return (
        _str(resource.get("date"))
        or _str(resource.get("created"))
        or _period_start(context.get("period"))
        or _str(resource.get("indexed"))
    )


def note_sort_key(resource: dict) -> str:
    return note_date(resource) or ""


def note(resource: dict, text: str | None) -> dict:
    type_text = concept_text(resource.get("type"))
    preview = None
    if text:
        preview = text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1].rstrip() + "…"
    return {
        "title": _str(resource.get("description")) or type_text or "Clinical note",
        "type": type_text,
        "date": note_date(resource),
        "author": reference_display(resource.get("author")),
        "status": _str(resource.get("docStatus")) or _str(resource.get("status")),
        "content_preview": preview,
        "has_full_text": bool(text) and len(text) <= PREVIEW_CHARS,
    }


# ---- ordering ----------------------------------------------------------------------------------------

_SORT_FIELD = {"medications": "authored_on", "labs": "effective_at", "encounters": "start", "notes": "date"}


def sort_newest_first(kind: str, items: list[dict]) -> list[dict]:
    field = _SORT_FIELD[kind]
    return sorted(items, key=lambda item: item.get(field) or "", reverse=True)
