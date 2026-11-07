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

- `elevenlabs/agent_configs/foggy.json`: system prompt (answers only from Jordan Lee's knee replacement care plan, which is embedded in the prompt; never changes a dose; 911 for chest pain, trouble breathing, heavy bleeding or fainting; short check-in), first message, LLM `gemini-3.5-flash` (temperature 0.2), voice "Sarah" (`EXAVITQu4vr4xnSDxMaL`, speed 0.9).
- `elevenlabs/agents.json`: maps the config file to the agent id.
- The agent is public (no signed URL) and only accepts browsers from `localhost:3000`, `cloudcare.icu` and `www.cloudcare.icu`. The browser connects with just `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` over WebRTC (`src/components/voice/VoiceSession.tsx`).

To change Foggy, edit `foggy.json` and push it (the CLI reads `ELEVENLABS_API_KEY` from the environment; it lives in `.env.local` and never goes in a `NEXT_PUBLIC_` variable):

```powershell
cd elevenlabs
npx -y @elevenlabs/cli@latest agents push
npx -y @elevenlabs/cli@latest agents status
```

The care plan text in the prompt is a copy of the demo plan in `backend/app/seed.py`. If that plan changes, update the prompt too.

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
