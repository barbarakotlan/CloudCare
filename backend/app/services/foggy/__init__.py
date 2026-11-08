"""Foggy behavior policy v2 (docs/foggy-policy.md).

The backend owns routing, conversation state and actions; text chat and the voice agent
are thin clients of POST /chat. The model classifies and phrases; code decides and acts.

  router.py    pre-checks, priority order, state transitions (answer_turn)
  classify.py  JSON-schema classifier call
  phrase.py    reply wording, two-sentence cap, 911 wording
  actions.py   capability-checked actions (message the care team, emergency alert, check-in save)
  state.py     chat_sessions load/save
  doses.py     today's due medicine doses for the check-in (one question per dose), dose logs,
               speech-friendly times and amounts; CHECKIN_TIMEZONE sets the patient's local day
  lexicon.py   emergency, call-trigger, dose-change, consent and check-in word lists
"""

from app.services.foggy.actions import capabilities
from app.services.foggy.router import TurnResult, answer_turn

__all__ = ["answer_turn", "TurnResult", "capabilities"]
