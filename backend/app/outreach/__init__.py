"""Foggy texts or calls the signed-in patient's own phone (Twilio SMS, ElevenLabs calls).

Setup for each dashboard: docs/phone-outreach.md.

Import the router from its module (`from app.outreach.router import router`). This
package file stays empty on purpose so `app.auth` can import `app.outreach.phone`
without a circular import (the router depends on `app.auth`).
"""
