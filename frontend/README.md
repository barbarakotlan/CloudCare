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
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI base URL. The backend's CORS allows `http://localhost:3000` only. |
| `NEXT_PUBLIC_AUTH_PROVIDER` | `backend` | `backend` = FastAPI `POST /auth/login` (JWT). `supabase` = Supabase email/password (dormant until a project exists; the backend does not accept Supabase tokens yet). |
| `NEXT_PUBLIC_SUPABASE_URL` | empty | Supabase project URL (only for the supabase provider). |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | empty | Supabase anon key (only for the supabase provider). |
| `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` | empty | ElevenLabs Conversational AI agent for "Talk to Foggy". Empty shows a friendly "not configured yet" state. |

## Routes

| Route | What |
|---|---|
| `/` | Landing: scripted Foggy conversation on a phone, "Try texting Foggy" (local demo chat), "Talk to Foggy" (voice). |
| `/login` | Doctor / Patient toggle, demo credentials prefilled, redirects by role. |
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
    supabase/          browser client (null when env vars are missing)
    demo/              demo care plan + scripted landing conversation + local Foggy answers
    hooks/             useAsync, usePolling, useNow, useReducedMotion
```

Session storage: `localStorage["cloudcare.token"]` and `localStorage["cloudcare.user"]`.
