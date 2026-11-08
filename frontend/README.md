# CloudCare frontend

Next.js 16 (App Router, Turbopack, Cache Components) + React 19 + Tailwind CSS v4.
Landing page, login, patient dashboard, clinician dashboard, Foggy chat and voice.

> Your head's in the clouds. Your care shouldn't be.

## Run it

```powershell
# from frontend/ (Windows PowerShell: put Node on PATH first)
$env:PATH = "C:\Program Files\nodejs;$env:PATH"
npm install
Copy-Item .env.local.example .env.local   # then edit if needed
npm run dev        # http://localhost:3000
npm run build      # production build (must pass)
npm run lint       # eslint 9 flat config
```

The backend must be running for login and the dashboards (from the repo root):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend   # http://localhost:8000
```

Demo accounts (seeded by the backend, password `demo123`):

| Role | Email |
|---|---|
| Patient (Jordan Lee) | `patient@demo.com` |
| Doctor (Dr. Priya Patel) | `clinician@demo.com` |

The landing page demo chat ("Try texting Foggy") works without the backend: it answers locally from the sample care plan in `src/lib/demo/`.

## Environment variables

All live in `frontend/.env.local` (template: `.env.local.example`).

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI base URL. The backend's allowed origins come from its `CORS_ORIGINS` env (default `http://localhost:3000`, `https://cloudcare.icu`, `https://www.cloudcare.icu`). |
| `NEXT_PUBLIC_AUTH_PROVIDER` | `backend` | `supabase` = Supabase Auth email/password, with patient sign-up (use this once the keys are set). `backend` = FastAPI `POST /auth/login` demo tokens; the offline fallback. |
| `NEXT_PUBLIC_SUPABASE_URL` | empty | Supabase project URL, `https://tvqmphtgtnzxhyszcdmi.supabase.co`. |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | empty | Supabase publishable key (`sb_publishable_...`). Public. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | empty | Legacy anon key; used only when the publishable key is empty. |
| `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` | empty | ElevenLabs Conversational AI agent for "Talk to Foggy". Empty shows a friendly "not configured yet" state. |

Never put a Supabase secret or `service_role` key in a `NEXT_PUBLIC_` variable: it would ship to every browser. The Supabase client refuses to start if it detects one.

## Sign-in with Supabase

With `NEXT_PUBLIC_AUTH_PROVIDER=supabase`:

- Sign-in uses `supabase.auth.signInWithPassword`, then calls the backend's `GET /auth/me` with the Supabase access token. The backend verifies the token against the project's signing keys and creates its own user row on first sign-in. If the backend rejects the token, the login form says so.
- The role comes from the backend (which reads `app_metadata.role`, set only by the server). `user_metadata` holds the display name and is never used for access decisions.
- "New patient? Create an account" on `/login` signs up a patient (`full_name` goes in `user_metadata`). If email confirmation is on, the form asks the user to confirm by email; the link returns to `/login`, which picks up the session. Add `http://localhost:3000/login` and `https://cloudcare.icu/login` to the Supabase Auth redirect URLs. Doctor accounts are not self-service.
- `src/components/app/SupabaseSessionSync.tsx` (mounted from the root layout only for this provider) restores the Supabase session on load and copies refreshed tokens into `cloudcare.token`, so API calls keep working past the one-hour token lifetime. Signing out in one tab signs out the others.
- The demo accounts (`patient@demo.com`, `clinician@demo.com`, password `demo123`) work with both providers once the backend has seeded them into Supabase.

## Voice ("Talk to Foggy")

Foggy's voice is an ElevenLabs agent, defined as config in `elevenlabs/` (agent id `agent_4701m6w1ey4demdt24zb8ngs4zac`):

Voice Foggy is a thin client of the backend: for a signed-in patient, every care-related turn goes to the same `POST /chat` the text chat uses, so routing, consent offers, check-in state and the 911 rule live in one place (`docs/foggy-policy.md`).

- `elevenlabs/agent_configs/foggy.json`: the system prompt, LLM `gemini-3.5-flash` (temperature 0), voice "Anna- Final" (`tH0OHWA5hSMw20lI7KDL`, speed 0.9), and one server tool. The prompt:
  - signed in: calls `ask_cloudcare` with the patient's exact words on every turn that is not small talk (questions, symptoms, medicines, check-in answers, and yes/no or a number answering Foggy's last question) and says `message.content` as it is, only reading "911" as "nine one one" and numbers and units as words. It never adds facts and never says anything was sent unless the reply says so;
  - handles small talk itself in one warm sentence, with no tool and no contact offer: hello, thanks, okay, will do, sounds good, hold on, goodbye;
  - demo (and a turn whose tool call fails): answers from the embedded demo plan for Jordan with the policy wording: at most two sentences, "Call nine one one now. I can't place emergency calls." first for emergencies, "Your care plan does not cover that. Would you like to contact your medical team?" for out-of-scope questions, the dose-change refusal, and on "yes" "This is a demo, so no message was sent. In the live app, this would go to your medical team." (after a failed tool call: "I couldn't send the message. Please call your medical team."). It never says the care team was notified;
  - phone calls: the agent's own first message is empty, so a call starts silently. A call-screening assistant asking who is calling gets "This is Foggy from Dr. Patel's care team, calling for {{patient_name}}'s recovery check-in." and Foggy then waits (`skip_turn`) for a real hello; a voicemail greeting triggers `voicemail_detection`, which leaves a one-sentence message and hangs up; a real hello gets the greeting and "Is now a good time?", and a yes starts the check-in through `/chat`. Goodbyes end the call (`end_call`).
- Built-in system tools on the agent: `end_call`, `skip_turn`, `voicemail_detection` (with the voicemail message).
- `elevenlabs/tool_configs/ask_cloudcare.json` + `elevenlabs/tools.json`: the one server (webhook) tool:

  | Tool | Request | What the agent reads back |
  |---|---|---|
  | `ask_cloudcare` | `POST https://cloudcare-api-q4zg.onrender.com/chat`, body `{message: <the patient's exact words>, source: "voice"}` | `message.content` (said as is), `route` |

  It sends `Authorization` from the `secret__patient_auth` dynamic variable and waits up to 120 s (Render's free tier can take ~50 s to wake). No tool sound plays while it waits; pre-tool speech is `auto` (a short "One moment." only when calls have been slow). The old `log_check_in` tool is gone: voice check-ins run through `/chat` like text check-ins.
- `elevenlabs/agents.json`: maps the config file to the agent id.
- The agent is public (no signed URL) and only accepts browsers from `localhost:3000`, `cloudcare.icu` and `www.cloudcare.icu`. The browser connects with just `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` over WebRTC (`src/components/voice/VoiceSession.tsx`) and sends its own greeting, "Hi {name}, this is Foggy, your recovery helper. How are you feeling today?", through the `first_message` override (the only prompt-level override the agent allows).

Dynamic variables, set per call by `VoiceSession.tsx` (placeholders in `foggy.json` make a call without them behave like the demo):

| Variable | Signed-in patient | Anyone else (landing page, clinicians) |
|---|---|---|
| `patient_name` | first name from the CloudCare session | `Jordan` |
| `patient_mode` | `signed_in` → Foggy relays turns to `/chat` | `demo` → Foggy answers from the demo plan embedded in the prompt, no tools |
| `secret__patient_auth` | `Bearer <CloudCare access token>` | `Bearer demo` |

The `secret__` prefix makes ElevenLabs bind the value only to tool headers: it is never sent to the language model and is redacted in stored conversations. A header written as a plain string such as `"Bearer {{token}}"` is not templated (the backend gets the literal text and returns 401), so the header uses the `{"variable_name": "secret__patient_auth"}` form and the browser sends the whole `Bearer …` value. Phone calls placed by the backend (`backend/app/outreach/calls.py`) send the same three variables, with a short-lived token made for the call.

The conversation state (a pending offer to message the care team, check-in progress) is stored per patient on the backend, so a voice call and the text chat share it; two people testing with the same demo account at the same time will see each other's state.

To change Foggy, edit the JSON and push it (the CLI reads `ELEVENLABS_API_KEY` from the environment; it lives in `.env.local` and never goes in a `NEXT_PUBLIC_` variable):

```powershell
cd elevenlabs
npx -y @elevenlabs/cli@latest tools push
npx -y @elevenlabs/cli@latest agents push
npx -y @elevenlabs/cli@latest agents status
```

Note: `tools add` creates the tool in ElevenLabs right away and overwrites the config file with a stub (even with `--dry-run`); write the real config afterwards and run `tools push`.

The demo care plan text in the prompt is a copy of the demo plan in `backend/app/seed.py`. If that plan changes, update the prompt too.

## Routes

| Route | What |
|---|---|
| `/` | Landing: scripted Foggy conversation on a phone, "Try texting Foggy" (local demo chat), "Talk to Foggy" (voice). |
| `/login` | Doctor / Patient toggle, demo credentials prefilled, redirects by role. Patient sign-up when the Supabase provider is on. |
| `/patient/dashboard` | Day N of recovery, care plan, reminders (mock), symptom check-in, Foggy chat, voice. |
| `/clinician/dashboard` | Escalation queue (polls every 5 s), patients by risk, patient drawer (check-ins, transcript, care plan upload). |

## Layout

```
src/
  app/                 routes, layout, globals.css (brand tokens in @theme inline)
  components/
    brand/             Wordmark (live text), CloudMark, Swoosh, CloudShape
    ui/                Button, Card, Badge, Input, SegmentedControl, Skeleton, Toast, Modal
    chat/              ChatPanel, MessageBubble, TypingIndicator, useChat
    phone/             IPhoneFrame, ScriptedConversation
    voice/             TalkToFoggy (ElevenLabs, lazy-loaded)
    landing/ patient/ clinician/ app/
  lib/
    api/               client.ts (bearer token, JSON errors), types.ts, one file per resource
                       reminders.ts is MOCK data until the backend ships medication/appointment routes
    auth/              provider switch (backend | supabase), session store, useSession, RequireRole
    supabase/          browser client (null when env vars are missing or the key is a secret key)
    demo/              demo care plan + scripted landing conversation + local Foggy answers
    hooks/             useAsync, usePolling, useNow, useReducedMotion
```

Session storage: `localStorage["cloudcare.token"]` and `localStorage["cloudcare.user"]`.
