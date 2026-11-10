# Phone outreach: "Test on my phone"

A patient gives a mobile number at sign-up (or adds it on the dashboard). From the dashboard they can check in right there, have Foggy **text** them a check-in link, or have Foggy **call** them for a spoken check-in. Every text and call goes only to the number stored on the signed-in patient's own profile. There is no way to type in a different destination, and emergency or service numbers (911, other N11 codes, short codes) are refused when the number is saved and again before anything is sent.

Status wording is literal: "Text sent" means the texting service accepted it for delivery, "Text delivered" appears only when the carrier reports delivery, and "Call started" means the phone is being dialed. Nothing claims a message was read or that a person was reached.

## How it works

| Piece | Where |
|---|---|
| Number on the profile | `patients.phone` (E.164, e.g. `+15551234567`) and `patients.phone_verified_at` (unused for now). SQL: `database/patient_phone.sql`. |
| Number at sign-up | "Mobile number (optional)" on the sign-up form (`LoginForm.tsx`), checked and converted to E.164 in the browser (`frontend/src/lib/phone.ts`, US default) and sent as `options.data.phone`; Supabase stores it in `user_metadata.phone`. On first sign-in the API copies it onto the new patient profile (`backend/app/auth.py`). An unusable number is ignored, never blocks sign-in. |
| Patient edits the number | `PATCH /patients/me {phone}` (patients only; any common format; `null` or `""` clears; 422 with a readable message for unusable numbers). `PatientOut.phone` returns it. |
| Clinician edits the number | `PATCH /patients/{id}` accepts `phone` too; the drawer's Overview shows "Mobile" and the Profile tab has the field. |
| Outreach API | `backend/app/outreach/` (router prefix `/outreach`, patients only) |
| History | `outreach_log` table (last four digits, channel, kind, status, provider id). SQL: `database/outreach.sql`. |
| Dashboard card | `frontend/src/components/patient/TestOnPhoneCard.tsx`, under the check-in card: the number (inline edit), "Check in here" (scrolls to the check-in), "Text me", "Call me". Buttons stay off with a short reason until the server is set up and a number is on file. |

### Endpoints

| Method + path | Body | Returns |
|---|---|---|
| `GET /outreach/capabilities` | none | `{sms, call, reasons: {sms?, call?, phone?}, phone_on_file, phone_last4, limits: {sms_seconds: 60, call_seconds: 120}}` |
| `POST /outreach/sms` | `{kind: "checkin" \| "plan_summary"}` | `{status: "sent" \| "failed", provider_id, to_last4, detail}` |
| `GET /outreach/sms/{provider_id}` | none | `{provider_id, delivery, failed, detail}` for the patient's own text from the last day |
| `POST /outreach/call` | `{kind: "checkin"}` | `{status: "started" \| "failed", conversation_id, to_last4, detail}` |

Errors: 503 when the channel isn't configured, 409 when there is no usable number on file, 429 (with `Retry-After`) inside the rate limit, 403 for clinicians.

Rate limits: one text per patient per 60 seconds, one call per patient per 2 minutes. Every attempt that reached the provider counts, so a double tap never sends twice. Enforced in memory and from `outreach_log`.

Texts are plain ASCII, at most 320 characters (two SMS segments), use the patient's first name, include the dashboard link, the 911 line, and "Reply STOP to opt out". The plan summary lists only care-plan section names, never doses or the procedure.

Calls pass the same dynamic variables as the browser voice session (`patient_name`, `patient_mode: "signed_in"`, `secret__patient_auth`), so the agent's `ask_cloudcare` tool reaches `/chat` as that patient. The bearer token in `secret__patient_auth` is a CloudCare token minted for that call only and expires after 30 minutes. ElevenLabs keeps `secret__` variables out of the model's prompt and stores them redacted.

Logs hold event names, HTTP status codes, provider error codes and the last four digits only.

## What the provider docs say (checked 2026-11-08)

### ElevenLabs outbound calls

- **Endpoint:** `POST https://api.elevenlabs.io/v1/convai/twilio/outbound-call`, header `xi-api-key: <key>`, JSON body:
  - `agent_id` (required), `agent_phone_number_id` (required), `to_number` (required, E.164)
  - `conversation_initiation_client_data` (optional) → `dynamic_variables` (map), plus `conversation_config_override`, `user_id`, and others
  - `telephony_call_config` (optional): `ringing_timeout_secs` (default 60), `twilio_machine_detection`, `twilio_call_recording_enabled`
  - Response 200: `{success, message, conversation_id, callSid}`. `success: false` with a Twilio message is how a Twilio refusal comes back.
  - Source: https://elevenlabs.io/docs/api-reference/twilio/outbound-call
- **`agent_phone_number_id`** is the id ElevenLabs gives a phone number after you import it. It appears as `phone_number_id` in `GET https://api.elevenlabs.io/v1/convai/phone-numbers` (response fields `phone_number`, `label`, `provider` (`twilio` / `sip_trunk` / ...), `phone_number_id`, `assigned_agent`). Source: https://elevenlabs.io/docs/api-reference/phone-numbers/list
- **Getting a number:** the ElevenLabs docs only describe importing a number you already own (Twilio native integration, or a SIP trunk). The Twilio integration page says the number "must be purchased through Twilio". There is no documented way to buy a number from ElevenLabs for this use. Source: https://elevenlabs.io/docs/agents-platform/phone-numbers/twilio-integration/native-integration
- **Import:** ElevenLabs dashboard → Agents → Phone Numbers (https://elevenlabs.io/app/agents/phone-numbers) → import from Twilio with Label, Phone Number, Twilio SID (Account SID, or an API key SID starting `SK`), Twilio Token (Auth Token, or the API key secret). ElevenLabs configures the Twilio number itself. A Twilio "verified caller ID" can also be imported but is outbound-only and cannot be assigned to an agent; a purchased Twilio number supports both directions.
- **Batch calls** (not used here, for reference): `POST /v1/convai/batch-calling/submit` with `call_name`, `agent_id`, `agent_phone_number_id`, `recipients: [{phone_number, conversation_initiation_client_data: {dynamic_variables}}]`. Source: https://elevenlabs.io/docs/api-reference/batch-calling/create
- **Dynamic variables:** `secret__` variables "should only be used in dynamic variable headers and never sent to an LLM provider"; the conversations API returns them as `<REDACTED>`, but post-call transcription webhooks receive the original values. Phone calls also get `system__caller_id`, `system__called_number`, `system__call_sid`. Source: https://elevenlabs.io/docs/agents-platform/customization/personalization/dynamic-variables

### Twilio texts

- **Endpoint:** `POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json`, HTTP Basic auth (`AccountSid:AuthToken`, or an API key SID and secret), form-encoded `To` (E.164), `From` (your Twilio number) or `MessagingServiceSid` (`MG...`), `Body` (up to 1,600 characters). The reply carries `sid` (`SM...`), `status` (`queued` or `accepted` at first; later `sending`, `sent`, `delivered`, `undelivered`, `failed`), `error_code`, `error_message`. Source: https://www.twilio.com/docs/messaging/api/message-resource
- Delivery problems that carriers report later (for example error 30034, unregistered US 10DLC number) only show up on the message's status, which is why the card checks `GET /outreach/sms/{sid}` a few times after sending.

### Twilio trial accounts (important)

From https://www.twilio.com/docs/usage/trials and the US trial guide (https://www.twilio.com/docs/messaging/guides/how-to-work-with-your-twilio-free-trial-account-us-only):

- Texts and calls only to **verified** numbers, up to 5 per account; the sign-up number is verified automatically; sign-up country only.
- Current trials use **shared Twilio-owned numbers** and SMS is limited to **pre-defined templates**: "Custom message bodies are not supported." A shared trial number is not yours, so it can't be imported into ElevenLabs either.
- After upgrading: custom message bodies, your own purchased numbers, no verified-recipient limit.
- **US texting needs carrier registration.** A US local (10DLC) number must be registered for A2P 10DLC before it can text US numbers, and that registration requires a paid account. A **toll-free** number needs Toll-Free Verification instead (free; can take several business days).

Practical consequence: for CloudCare's own texts and for calls through ElevenLabs, plan on an **upgraded (pay-as-you-go) Twilio account with a purchased number**. Calls work as soon as the number is bought and imported. Texts work once the number's registration (A2P 10DLC brand + campaign, or toll-free verification) is approved; until then Twilio accepts the text and the carrier blocks it, which the card reports as "wasn't delivered" with the reason.

## Setup Jacob must do (cannot be automated)

### 1. Database (Supabase SQL editor), before deploying the API

1. Run `database/patient_phone.sql`. **Do this before the new API version goes live**: every patient query selects the new columns, so the API errors until they exist. It is additive and safe to run early.
2. Run `database/outreach.sql`.
3. Each file ends with a check query; confirm the expected rows.

### 2. Twilio (https://console.twilio.com)

1. Sign in or create an account. Upgrade to a paid (pay-as-you-go) account: Admin → Account billing → Upgrade. A trial cannot send custom texts and its shared number can't be imported into ElevenLabs.
2. Buy a number with Voice and SMS: Phone Numbers → Manage → Buy a number → United States → check Voice and SMS. A local number is cheapest; a toll-free number has a simpler verification for texting.
3. For texting, register the number:
   - Local number: Messaging → Regulatory Compliance → A2P 10DLC → register a brand (Sole Proprietor is the lightest option for an individual) and a campaign (use case e.g. "Account notifications"; sample message: the check-in text below; opt-out "Reply STOP"). Add the number to the campaign's Messaging Service.
   - Toll-free number: Phone Numbers → the number → Toll-free verification → submit the business and use-case details.
   - Approval can take days. Calls do not wait for this.
4. Copy the Account SID and Auth Token: Console home → Account Info. Better: Account → API keys & tokens → Create API key (Standard) and use its SID (`SK...`) and secret for the ElevenLabs import.
5. Optional: if the number sits in a Messaging Service (10DLC campaigns do), copy the Messaging Service SID (`MG...`) for `TWILIO_MESSAGING_SERVICE_SID`; texts are then sent through the service.

### 3. ElevenLabs (https://elevenlabs.io/app/agents)

1. Agents → Phone Numbers → Import number → From Twilio: Label "CloudCare", the Twilio number in E.164, Twilio SID, Twilio Token. Save.
2. Assign the Foggy agent (`agent_4701m6w1ey4demdt24zb8ngs4zac`) to the number for inbound calls if wanted (outbound calls name the agent per request anyway).
3. Copy the number's id: click the number in the Phone Numbers list (or `GET /v1/convai/phone-numbers` with the API key and read `phone_number_id`). This is `ELEVENLABS_PHONE_NUMBER_ID`.
4. Test from the dashboard: Phone Numbers → Outbound call next to the number → choose Foggy → enter your mobile → Send Test Call.
5. API key for the backend: Profile → API keys → create a key restricted to Agents (ElevenAgents) write access. This is the backend copy of `ELEVENLABS_API_KEY` (separate from the one in `frontend/.env.local`).
6. The agent's first message uses `{{patient_name}}`, and its tools use `secret__patient_auth`; both are sent by the API on every call. No agent change is required for calling to work.

### 4. Render (cloudcare-api → Environment)

| Variable | Value |
|---|---|
| `OUTREACH_ENABLED` | `true` to allow texts and calls; default off (both buttons show "Calls and texts from Foggy are paused." and nothing reaches Twilio or ElevenLabs) |
| `TWILIO_ACCOUNT_SID` | `AC...` |
| `TWILIO_AUTH_TOKEN` | Auth Token (secret) |
| `TWILIO_FROM_NUMBER` | the Twilio number, E.164 |
| `TWILIO_MESSAGING_SERVICE_SID` | optional, `MG...` (used instead of `From` when set) |
| `ELEVENLABS_API_KEY` | backend key from step 3.5 (secret) |
| `ELEVENLABS_AGENT_ID` | `agent_4701m6w1ey4demdt24zb8ngs4zac` |
| `ELEVENLABS_PHONE_NUMBER_ID` | from step 3.3 |
| `PUBLIC_APP_URL` | `https://cloudcare.icu` (default) |
| `OUTREACH_ALLOWED_COUNTRY_CODES` | optional, default `1` (US/Canada only); comma-separated country codes |

Then Manual Deploy. `GET /outreach/capabilities` (signed in as a patient) shows `sms: true` / `call: true` once the variables are in.

Calls placed from a **local** API mint tokens with the local `JWT_SECRET`, but the agent's tool calls the Render API, which rejects them unless both use the same secret. Test calls from cloudcare.icu, or point the tool at a tunnel for local testing.

## Example texts

Check-in (`kind: "checkin"`):

> Hi Jordan, it's Foggy from CloudCare. Time for your recovery check-in. It takes about a minute: https://cloudcare.icu/patient/dashboard#check-in For chest pain or trouble breathing, call 911. Reply STOP to opt out.

Plan summary (`kind: "plan_summary"`):

> Hi Jordan, it's Foggy from CloudCare. Your care plan covers: Wound care, Activity, Pain and swelling, Medications, When to call. Read it any time: https://cloudcare.icu/patient/dashboard For chest pain or trouble breathing, call 911. Reply STOP to opt out.

## Verify end to end (after the setup above)

1. On https://cloudcare.icu, sign in as the demo patient (it has a care plan) and add your own mobile number in the "Test on my phone" card, or create a new patient account with your number at sign-up (new accounts have no care plan until a clinician adds one). The card shows the number formatted, for example "(555) 123-4567". Remove your number from the shared demo account afterwards.
2. "Text me": the card shows "Text sent to ···1234", then "Text delivered" within about 15 seconds. If it shows "wasn't delivered" with a carrier reason, the number's texting registration is still pending.
3. Wait for the button to come back (60 s). "Call me": the card shows "Call started"; the phone rings from the Twilio number; Foggy greets you by first name. Ask "Can I shower?": on the demo account the answer comes from its care plan, which means the call's tool access works.
4. ElevenLabs → Agents → Calls History shows the call. `outreach_log` has one `sms` row and one `call` row with only the last four digits.
5. Pressing "Text me" twice quickly sends one text; the second press is held for the rest of the minute.

## Not done yet

- No number confirmation (one-time code) flow; `phone_verified_at` stays empty. Because a patient could enter someone else's number, sends are rate-limited and the content is generic.
- Call outcome (answered, voicemail, ended) is not tracked; the card says only that the call started.
- Inbound texts (replies other than STOP/START, which Twilio handles) are not processed.
