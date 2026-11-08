"""Per-user request limits for routes that cost money or write shared state.

Use as `@router.post(..., dependencies=[Depends(limit_chat)])`. Limits are generous
for a person and tight for a script (see app.security.RateLimiter for the caveats).
"""

from fastapi import Depends

from app.auth import get_current_user
from app.models import User
from app.security import RateLimiter, too_many

# Each Foggy turn may call the language model twice; voice sends one turn per utterance.
CHAT = RateLimiter("chat", limit=30, window=60)
CHECKIN = RateLimiter("checkin", limit=20, window=60)
CARE_PLAN = RateLimiter("care-plan", limit=30, window=60)
EPIC_START = RateLimiter("epic-start", limit=10, window=60)
# Shared demo patient: anyone with the public demo login can reset it.
DEMO_RESET = RateLimiter("demo-reset", limit=5, window=60)


def limit_chat(user: User = Depends(get_current_user)) -> None:
    wait = CHAT.hit(str(user.id))
    if wait:
        raise too_many("You're sending messages very quickly.", wait)


def limit_checkin(user: User = Depends(get_current_user)) -> None:
    wait = CHECKIN.hit(str(user.id))
    if wait:
        raise too_many("Too many check-ins in a short time.", wait)


def limit_care_plan(user: User = Depends(get_current_user)) -> None:
    wait = CARE_PLAN.hit(str(user.id))
    if wait:
        raise too_many("Too many care plan uploads in a short time.", wait)


def limit_epic_start(user: User = Depends(get_current_user)) -> None:
    wait = EPIC_START.hit(str(user.id))
    if wait:
        raise too_many("Too many MyChart sign-in attempts.", wait)


def limit_demo_reset(user: User = Depends(get_current_user)) -> None:
    # Per account: the public demo logins are one account each, so this still bounds them.
    wait = DEMO_RESET.hit(str(user.id))
    if wait:
        raise too_many("The demo was just reset.", wait)
