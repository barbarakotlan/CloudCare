"""Phone number checks shared by sign-up, the profile edit and outreach.

Numbers are stored in E.164 (`+15551234567`). Anything that could reach an emergency
or special service (911, N11 codes, short codes) is rejected, so CloudCare can never
text or call one of them.
"""

import re

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
# North American Numbering Plan: +1 NXX NXX XXXX, N = 2-9.
_NANP = re.compile(r"^\+1([2-9]\d{2})([2-9]\d{2})(\d{4})$")
# Emergency and service numbers used around the world. They are far too short to be
# valid E.164 subscriber numbers, but the check keeps the intent explicit.
_EMERGENCY = {"911", "112", "999", "000", "110", "119", "100", "101", "102", "108", "111", "118", "120", "122", "190", "192", "193", "199"}


class PhoneError(ValueError):
    """The number can't be used. The message is safe to show to the patient."""


def _digits_and_plus(raw: str) -> str:
    raw = raw.strip()
    plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    return ("+" if plus else "") + digits


def normalize_e164(raw: str | None, default_country_code: str = "1") -> str:
    """Turns what a person typed into E.164, or raises PhoneError.

    US default: "(555) 234-5678" and "555.234.5678" become "+15552345678";
    "1 555 234 5678" too. Numbers in other countries must start with "+".
    """
    if raw is None or not str(raw).strip():
        raise PhoneError("Enter a mobile number.")
    cleaned = _digits_and_plus(str(raw))
    bare = cleaned.lstrip("+")
    if bare in _EMERGENCY or len(bare) <= 6:
        raise PhoneError("That number can't be used. Enter your own mobile number.")

    if not cleaned.startswith("+"):
        if default_country_code == "1" and len(bare) == 11 and bare.startswith("1"):
            cleaned = "+" + bare
        elif len(bare) == 10 and default_country_code:
            cleaned = f"+{default_country_code}{bare}"
        else:
            raise PhoneError("Enter a 10-digit US number, or start with + and your country code.")

    if not _E164.match(cleaned):
        raise PhoneError("That doesn't look like a mobile number. Check the digits and try again.")

    if cleaned.startswith("+1"):
        m = _NANP.match(cleaned)
        if not m:
            raise PhoneError("That isn't a valid US or Canadian number. Check the area code.")
        area, exchange, _ = m.groups()
        # N11 codes (211, 311, 411, 511, 611, 711, 811, 911) are service numbers, never subscribers.
        if area[1:] == "11" or exchange[1:] == "11":
            raise PhoneError("That number can't be used. Enter your own mobile number.")
    return cleaned


def is_usable_e164(value: str | None) -> bool:
    """True when a stored value is a number CloudCare may text or call."""
    if not value:
        return False
    try:
        return normalize_e164(value) == value
    except PhoneError:
        return False


def last4(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-4:] if len(digits) >= 4 else ""
