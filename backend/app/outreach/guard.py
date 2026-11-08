"""Abuse limits for texts and calls on top of the per-patient interval in log.py.

The destination is always the patient's own stored number, but a patient (or anyone
holding the public demo login) can change that number. Without extra limits the
"Call me" button could be pointed at a stranger's phone. These checks bound that:

- New-number cooldown: no text or call within OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS
  (default 10 minutes) of the number being set or changed, so numbers can't be cycled.
- Per-destination daily cap: at most OUTREACH_MAX_PER_NUMBER_PER_DAY texts and the same
  number of calls (default 6 each) to one phone number, across every account.
- Per-patient daily cap: at most OUTREACH_MAX_PER_PATIENT_PER_DAY per channel
  (default 10), counted from the outreach_log table.
- Server-wide hourly cap on calls: OUTREACH_MAX_CALLS_PER_HOUR (default 30) bounds cost.

The first, second and fourth are in memory (one Render process; they reset on restart).
Residual risk and the longer-term fix (verifying the number with a one-time code) are
in docs/security-review.md.

No imports from app.auth here: auth.py records sign-up numbers through this module.
"""

import os
import threading
import time
import uuid

from app.security import RateLimiter

DAY = 24 * 60 * 60


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int((os.getenv(name) or "").strip())
    except ValueError:
        return default
    return min(max(value, lo), hi)


def new_number_cooldown_seconds() -> int:
    return _env_int("OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS", 600, 0, DAY)


def max_per_patient_per_day() -> int:
    return _env_int("OUTREACH_MAX_PER_PATIENT_PER_DAY", 10, 1, 1000)


_lock = threading.Lock()
_phone_changed: dict[uuid.UUID, float] = {}

_per_number = RateLimiter("outreach-number", _env_int("OUTREACH_MAX_PER_NUMBER_PER_DAY", 6, 1, 1000), DAY)
_calls_hourly = RateLimiter("outreach-calls-hourly", _env_int("OUTREACH_MAX_CALLS_PER_HOUR", 30, 1, 10_000), 3600)


def reset() -> None:
    """Tests only."""
    with _lock:
        _phone_changed.clear()
    _per_number.clear()
    _calls_hourly.clear()


def note_phone_change(patient_id: uuid.UUID) -> None:
    """Call whenever a patient's number is set to a new value (sign-up, profile edit, clinician edit)."""
    with _lock:
        _phone_changed[patient_id] = time.monotonic()


def new_number_wait(patient_id: uuid.UUID) -> int:
    """Seconds until a recently set number may be texted or called (0 = allowed)."""
    cooldown = new_number_cooldown_seconds()
    with _lock:
        changed = _phone_changed.get(patient_id)
    if changed is None or cooldown <= 0:
        return 0
    elapsed = time.monotonic() - changed
    return max(0, int(cooldown - elapsed + 0.999))


def number_wait(channel: str, e164: str) -> int:
    """Seconds until this destination may get another text/call on this channel (0 = allowed)."""
    return _per_number.blocked(f"{channel}:{e164}")


def global_call_wait() -> int:
    return _calls_hourly.blocked("calls")


def count_attempt(channel: str, e164: str) -> None:
    """Counts one attempt that reached the provider against the destination and global caps."""
    _per_number.hit(f"{channel}:{e164}")
    if channel == "call":
        _calls_hourly.hit("calls")
