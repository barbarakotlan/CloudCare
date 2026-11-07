# CloudCare — working context for Claude

Last updated: 2026-11-07 (orchestrator: Fable; builder: Opus 5.5). Keep this file current: it is the single source of truth any agent reads before touching the repo.

## What CloudCare is

Post-operative recovery companion for a hackathon ("In the Clouds" theme, anesthesiology). Patients are handed critical recovery instructions while still foggy from anesthesia and forget them. CloudCare brings the care team's guidance home: a personalized plan, reminders, a chatbot named **Foggy** that answers only from the clinician's care plan, symptom check-ins scored by an ML risk model, and human-in-the-loop escalation to the clinician.

Slogan (render as live text, never only as an image): **Your head's in the clouds. Your care shouldn't be.**

Tracks: Ethical AI Agent, ML and Data Science, Healthcare. Ethical story: Foggy answers only from the care plan, declines and logs what it cannot answer, never changes a dose, humans close every escalation.

## Team and ownership (do not edit folders you do not own)

| Person | Owns | Builds |
|---|---|---|
| **Jacob (this repo checkout, branch `jacob/frontend`)** | `frontend/` | Landing page, login, patient dashboard, clinician dashboard, chat UI, voice |
| Barbara | `database/`, `backend/app/` except `services/` | Schema, FastAPI, auth, routes |
| Anna | `backend/app/services/`, `ml/` | Foggy RAG, red-flag detection, synthetic data, XGBoost risk model |

Rule for agents working for Jacob: **only write inside `frontend/`** (plus this `CLAUDE.md`). Never edit `backend/`, `database/`, `ml/`. If the backend needs a change, write it down in the "Asks for teammates" section below instead.

## Repo, branch, environment

- Repo: `C:\Users\jacob\OneDrive\Documents\GitHub\CloudCare` (remote `https://github.com/barbarakotlan/CloudCare.git`).
- Work on branch **`jacob/frontend`**, created from `origin/main` at `9ed72c8` (Barbara's backend PR merged). Merge back into `main` via PR later. Never commit to `main` directly.
- Commit often with clear messages. Do not push unless Jacob asks.

### Tooling on this Windows machine (PATH is minimal in the agent shell; use full paths)

| Tool | Path | Notes |
|---|---|---|
| git | `C:\Users\jacob\AppData\Local\GitHubDesktop\app-3.6.10\resources\app\git\cmd\git.exe` | 2.56. Bundled with GitHub Desktop. |
| node / npm | `C:\Program Files\nodejs\node.exe`, `C:\Program Files\nodejs\npm.cmd` | Node v26.13.0, npm 11.20.0. Prepend `C:\Program Files\nodejs` to `$env:PATH` in each PowerShell call. |
| uv | `C:\Users\jacob\.local\bin\uv.exe` | 0.13.7. Python is managed by uv (3.14 installed). |
| Python venv | `<repo>\.venv` | Created with `uv venv .venv --python 3.14`. Backend deps installed via `uv pip install --python .venv\Scripts\python.exe -r backend\requirements.txt`. |
| VS Code | `code` is on PATH | Jacob edits here. |

PowerShell 5.1: no `&&`. Chain with `;` or `if ($?) { ... }`.

### Commands

```powershell
# frontend (run from frontend/)
$env:PATH = "C:\Program Files\nodejs;$env:PATH"
npm install
npm run dev        # http://localhost:3000
npm run build      # must pass before any commit is considered done
npm run lint       # eslint 9 flat config (next core-web-vitals + typescript)

# backend (run from repo root). SQLite fallback when DATABASE_URL unset; seeds demo users on startup.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend   # http://localhost:8000, docs at /docs
```

## Tech stack (actual versions in the repo)

- **Frontend**: Next.js **16.4.5** (App Router, Turbopack, `cacheComponents: true`, `partialPrefetching: true`), React **19.3**, TypeScript 5, **Tailwind CSS v4** (`@import "tailwindcss"` + `@theme inline`, loaded through `@tailwindcss/turbopack`; there is no tailwind.config file). ESLint 9 flat config.
  - **This Next.js is newer than training data.** Before writing code, read `frontend/node_modules/next/dist/docs/` (the `frontend/AGENTS.md` block is auto-added by `next dev` and says the same). Heed deprecations. `cacheComponents` means dynamic data access (cookies, fetch without cache, `searchParams`) must sit inside `<Suspense>` or be in client components; simplest path for the hackathon is client components fetching the API with hooks.
  - Path alias `@/*` → `frontend/src/*`.
- **Backend**: FastAPI 0.162 + SQLAlchemy 2.1, PyJWT, psycopg (Postgres) or SQLite fallback. CORS allows `http://localhost:3000` only.
- **Auth**: Barbara shipped a working demo login (JWT bearer). See API contract. Supabase is scaffolded on the frontend as an optional provider (see "Auth decision").
- **Voice**: ElevenLabs Conversational AI (Agents). Frontend uses `@elevenlabs/react` (`useConversation`) for in-browser "Talk to Foggy"; phone calls go through ElevenLabs + Twilio on the backend later. Set up via `npx -y @elevenlabs/cli@latest onboard init` (see Status).
- **Texting AI**: Foggy chat hits `POST /chat` on the backend; Anna replaces `services/ai_service.py` with the real LLM + RAG. The frontend does not call an LLM directly.

## Backend API contract (what the frontend consumes)

Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). All routes except `/auth/login`, `/`, `/health` need `Authorization: Bearer <access_token>`.

### Demo accounts (seeded on backend startup, password `demo123`)

| Role | Email | Name | Notes |
|---|---|---|---|
| patient | `patient@demo.com` | Jordan Lee | Total knee replacement (right), orthopedic, surgery 3 days ago, diabetes. Has an active care plan with sections: Wound care, Activity, Pain and swelling, Medications, When to call. |
| clinician | `clinician@demo.com` | Dr. Priya Patel | Jordan's assigned clinician. |

### Endpoints

| Method + path | Who | Body / query | Returns |
|---|---|---|---|
| `POST /auth/login` | anyone | `{email, password}` | `{access_token, user: {id, full_name, role: 'patient'|'clinician'}}` |
| `GET /auth/me` | any user | — | `{id, full_name, role}` |
| `GET /patients` | clinician | — | `PatientRow[]` sorted highest risk first: `{id, full_name, procedure_name, surgery_date, latest_risk: RiskOut|null, open_escalations, last_checkin_at}` |
| `GET /patients/me` | patient | — | `PatientOut {id, full_name, procedure_name, procedure_type, surgery_date, discharge_date, comorbidities: string[]}` |
| `GET /patients/me/care-plan` | patient | — | `CarePlanOut {id, title, raw_text, created_at, chunks: [{id, chunk_index, section, content}]}` or `null` |
| `GET /patients/{id}` | clinician | — | `PatientOut` |
| `POST /patients/{id}/care-plan` | clinician | `{title, raw_text}` (blank-line separated blocks; a short first line ending in `:` becomes the section name) | `CarePlanOut` (201) |
| `POST /symptoms` | patient | `SymptomIn {pain_level 0-10, temperature_f?, wound_redness, wound_drainage, swelling, nausea, shortness_of_breath, mobility_level 0-4 (default 4), free_text?, source: 'checkin'|'chat'|'voice'}` | `{symptom_log_id, risk: RiskOut, escalated}` (201) |
| `GET /symptoms?patient_id=` | patient (own) / clinician (must pass patient_id) | — | `SymptomOut[]` newest first |
| `POST /chat` | patient | `{message}` | `{message: ChatMessageOut, escalated}` |
| `GET /chat/history?patient_id=` | patient (own) / clinician (must pass patient_id) | — | `ChatMessageOut[]` oldest first |
| `GET /escalations?status=active|open|acknowledged|resolved|all` | clinician | — | `EscalationOut[]` most urgent first |
| `PATCH /escalations/{id}` | clinician | `{status: 'open'|'acknowledged'|'resolved', clinician_notes?}` | `EscalationOut` |
| `GET /health` | anyone | — | `{status, database}` |

Shapes:
- `RiskOut {score: number 0-1, risk_level: 'low'|'medium'|'high', top_factors: [{feature, impact}], model_version, created_at}`
- `ChatMessageOut {id, role: 'patient'|'assistant'|'clinician', content, citations: [{chunk_id, section}], answered_from_plan: boolean|null, red_flag: boolean, created_at}`
- `EscalationOut {id, patient_id, patient_name, trigger_type: 'red_flag'|'high_risk'|'unanswered_question'|'patient_request', severity: 'low'|'medium'|'high'|'emergency', summary, status, clinician_notes, created_at, resolved_at}`

**Not in the backend yet** (tables exist in `database/scheme.sql` but no routes): `medications`, `medication_logs`, `appointments`. The frontend uses typed mock data behind the same `api/` layer for these, so swapping to real routes later is a one-file change. See "Asks for teammates".

Errors: 401 `Not logged in`, 403 `Clinicians only` / `Patients only`, 404 `Patient not found`, 422 validation (FastAPI `{detail: ...}`).

## Auth decision

Jacob asked for Supabase login. Barbara's backend already authenticates with its own JWT and every protected route requires that token, so for the demo the frontend logs in against `POST /auth/login` and stores the token (localStorage key `cloudcare.token`, user JSON under `cloudcare.user`). Supabase is wired as an optional provider:

- `frontend/src/lib/auth/` exposes one interface (`login(email, password, role)`, `logout()`, `getSession()`, `getToken()`), with `backend` and `supabase` implementations chosen by `NEXT_PUBLIC_AUTH_PROVIDER` (default `backend`).
- `@supabase/supabase-js` is installed; `frontend/src/lib/supabase/client.ts` creates the browser client from `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Env template in `frontend/.env.local.example`. A Supabase project must be created by Jacob (account creation cannot be automated); until then the Supabase provider is dormant.
- If the team later moves the backend to verify Supabase JWTs, only the provider file changes.

## Brand (source of truth: the supplied logos in `frontend/public/brand/`)

Web-ready crops were produced from the originals in `C:\Users\jacob\Downloads` (whitespace removed, outer white made transparent, enclosed white heart preserved; originals untouched):

| File | Use |
|---|---|
| `cloudcare-symbol.png` (1988×962) | Standalone red cloud with white heart. Nav mark, favicon source, decorative. |
| `cloudcare-slogan.png` (1926×665) | Wordmark + swoosh + slogan line. Brand reference only; slogan on the homepage is live text. |
| `cloudcare-powered-by-jab.png` (1933×511) | Footer / attribution. |
| `icon-512.png`, `icon-192.png`, `icon-64.png` | App icons / favicon. |

Colors (define as CSS variables in `globals.css` and expose via `@theme inline` so Tailwind utilities like `bg-brand-cyan` exist):

| Token | Hex | Role |
|---|---|---|
| `--brand-red` | `#DC3849` | Selective accents, "Cloud" in wordmark, red cloud |
| `--brand-red-dark` | `#C2303F` | Shadow tone inside the logo; hover for red |
| `--brand-cyan` | `#199AC0` | Primary interactive controls, "Care" in wordmark, links |
| `--brand-white` | `#FFFFFF` | Page background |
| `--brand-gray` | `#636363` | Supporting text, "powered by" |
| `--surface-pale` | `#E5F4F8` | Airy pale-blue section backgrounds, neutral bubbles |
| `--ink` | dark neutral such as `#1C2630` | Body text |

Page is predominantly white with pale-blue sections. Cyan for primary buttons. Red sparingly. Wordmark in HTML: "Cloud" red, "Care" cyan.

Typography: clean, friendly humanist sans-serif that complements the wordmark (the logo lettering is close to Trebuchet/Candara). Use a Google font via `next/font` such as **Nunito** (headlines + body) or **Outfit**/**Plus Jakarta Sans**; confident headline scale, generous spacing. Carry the cloud's rounded shapes (large radii, pill buttons) and the swoosh's gentle curve (a subtle SVG curve divider or underline accent) into a few details. Feel: approachable, caring, professional.

## Frontend scope (Jacob's deliverables)

Layout reference: **Poke** (poke.com) landing page: centered iPhone with a live conversation, one confident headline, two actions, lots of white space. Adapt to CloudCare branding. Fetch poke.com once to confirm composition before designing.

### Routes

| Route | Purpose |
|---|---|
| `/` | Landing. Nav: symbol + wordmark, "Log in". Hero: headline, slogan as live text, prominent iPhone mockup playing a Foggy conversation (auto-advancing scripted messages, cyan patient bubbles / neutral Foggy bubbles, typing indicator; built with CSS/React, a `<video>` slot is fine if an asset appears later). Primary CTA **"Try texting Foggy"** opens an interactive demo chat (same ChatPanel component as the patient dashboard, demo mode with scripted/local responses from the demo care plan, no login). Secondary CTA **"Talk to Foggy"** opens the voice demo (ElevenLabs `useConversation`; graceful fallback message when `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` is unset). Sections: how it works (clinician enters plan → Foggy follows up → escalation to a human), the ethical-AI promise, tracks/footer with "powered by JAB Inc" image. Accessible: landmarks, alt text, focus states, reduced-motion respected. |
| `/login` | Doctor / Patient segmented toggle, email + password, demo-credential hints prefilled per role, calls auth provider, redirects by role to `/clinician/dashboard` or `/patient/dashboard`. Shows API errors. |
| `/patient/dashboard` | For Jordan Lee. Greeting + procedure + day N of recovery. Cards: today's plan (care plan sections rendered from `GET /patients/me/care-plan`), medication and appointment reminders (mock until backend routes exist, with "mark taken"), symptom check-in form (`POST /symptoms`) that shows the returned risk level and whether the care team was alerted, Foggy chat (`POST /chat`, `GET /chat/history`) with citations shown as small section chips and a visible "sent to your care team" state when `escalated` is true, voice button (ElevenLabs). Mobile-first. |
| `/clinician/dashboard` | For Dr. Patel. Escalation queue at top (`GET /escalations`, acknowledge/resolve via PATCH, severity colors: emergency red, high orange, medium amber, low gray; poll every 5 s so a new escalation appears during a demo). Patient table (`GET /patients`) with risk badge, open escalations, last check-in. Patient detail drawer/page: profile, symptoms (`GET /symptoms?patient_id=`), chat transcript (`GET /chat/history?patient_id=`), unanswered questions, care plan upload textarea (`POST /patients/{id}/care-plan`). |

### Architecture inside `frontend/src`

```
app/                  routes above (+ layout.tsx, globals.css, not-found)
components/
  brand/              Wordmark.tsx (live text), CloudMark.tsx, Swoosh.tsx (SVG)
  ui/                 Button, Card, Badge, Input, SegmentedControl, Skeleton, Toast
  chat/               ChatPanel.tsx, MessageBubble.tsx, TypingIndicator.tsx, useChat.ts
  phone/              IPhoneFrame.tsx, ScriptedConversation.tsx
  voice/              TalkToFoggy.tsx (ElevenLabs)
  patient/, clinician/  page-specific blocks
lib/
  api/                client.ts (fetch wrapper adding bearer token, JSON errors), types.ts (mirrors backend schemas), patients.ts, chat.ts, symptoms.ts, escalations.ts, reminders.ts (mock)
  auth/               index.ts (interface + provider switch), backend.ts, supabase.ts, useSession.ts, RequireRole.tsx
  supabase/           client.ts
  demo/               demoCarePlan.ts, foggyScript.ts (scripted landing conversation + local demo answers)
```

Conventions: TypeScript strict, no `any`. Client components only where interactive (`"use client"`). Keep server components for static landing sections. No new UI libraries beyond Tailwind; small headless pieces are hand-written. Icons: inline SVG or `lucide-react` (allowed). Commit after each route works.

### Definition of done for the frontend

1. `npm run build` and `npm run lint` pass with zero errors.
2. Backend running locally → login as both demo users → each dashboard loads real data; sending a chat message returns Foggy's reply; a check-in with pain 9 + shortness of breath produces an escalation that appears on the clinician dashboard within 5 s.
3. Landing page matches the brand brief, both CTAs work (voice degrades gracefully without an agent id), keyboard navigable, no horizontal scroll at 375 px.
4. Screenshots of `/`, `/login`, both dashboards at desktop and 375 px saved to `frontend/docs/screenshots/` (gitignored? no: commit them, they are small PNGs ≤ 300 KB each).

## Environment files

`frontend/.env.local.example` (copy to `.env.local`):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AUTH_PROVIDER=backend
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_ELEVENLABS_AGENT_ID=
```

Backend: `backend/.env.example` has `DATABASE_URL` and `JWT_SECRET`; unset `DATABASE_URL` → SQLite file `backend/cloudcare.db`.

## ElevenLabs setup

Ran once from `frontend/` on 2026-11-07: `npx -y @elevenlabs/cli@latest onboard init` (exit 0, non-interactive). It changed no files and printed this JSON (verbatim):

```json
{"details":{"env_file":".env.local"},"instruction":"Tell the user `say`, then run `run`.","next":"run","rules":["Never open, print or cat the env file; run `onboard check` to verify it.","Never ask for an API key in chat, and never accept one pasted there.","Never put the key in code; the SDK reads ELEVENLABS_API_KEY.","Never run git clean or delete untracked files.","Don't write or change any code until a reply's `next` is `write_code` or `load_key`.","Put anything you download only to read, like a package or an archive, in a temp folder, never in the project.","Don't run the app (or its start script) or make speech to try it until the user says yes to the test request. API calls that what they asked for needs, like creating an agent, are fine. Once the code is written, run `onboard check` before you finish: it verifies the key and the code."],"run":"npx -y @elevenlabs/cli@latest onboard connect --env-path .env.local","say":"Next, I'll open the ElevenLabs approval page in your browser. Sign in (or create an account) and click Authorize."}
```

The next step needs a browser sign-in, so it was not run. Remaining manual steps for Jacob (from `frontend/`, Node on PATH):

1. `npx -y @elevenlabs/cli@latest onboard connect --env-path .env.local` → sign in / create the ElevenLabs account in the browser and click Authorize. This writes `ELEVENLABS_API_KEY` into `frontend/.env.local` (server-only; never commit it, `.env*` is gitignored).
2. Create a Conversational AI agent named Foggy (CLI `onboard` flow, or the ElevenLabs dashboard). System prompt: answer only from the patient's care plan, decline and say the care team was notified otherwise, never change doses, tell the patient to call 911 for chest pain / trouble breathing. Make it a public agent (no signed URL) for the demo.
3. Put its id in `frontend/.env.local` as `NEXT_PUBLIC_ELEVENLABS_AGENT_ID=...` and restart `npm run dev`.
4. `npx -y @elevenlabs/cli@latest onboard check` to verify.
5. Later (backend/Anna): give the agent the care plan (knowledge base or a server tool hitting the backend) and wire phone calls via Twilio.

Frontend side is done: `src/components/voice/TalkToFoggy.tsx` lazy-loads `VoiceSession.tsx` (`ConversationProvider` + `useConversation`, `connectionType: "webrtc"`). The microphone is requested only when the user presses "Start talking". Without the agent id the panel shows "Voice demo not configured yet".

## Asks for teammates (frontend needs these; do not implement them yourself)

- **Barbara**: routes for `GET /patients/me/medications`, `POST /medications/{id}/logs` (mark taken/skipped), `GET /patients/me/appointments`, and clinician-side create endpoints. Also `GET /patients/{id}/care-plan` for clinicians (today only the patient can read the active plan). CORS: add the Vercel URL when deployed.
- **Barbara**: datetimes from SQLite come back without a timezone (`2026-11-07T19:46:16`). The frontend treats offset-less values as UTC (`parseApiDate` in `src/lib/format.ts`); returning timezone-aware ISO strings would remove the guesswork.
- **Barbara**: `GET /chat/history` does not say whether a message escalated; the UI infers it from `red_flag || answered_from_plan === false` (matches today's `routes/chat.py`). If escalation rules change, add an `escalated` field to `ChatMessageOut`.
- **Barbara (later)**: `PATCH /escalations/{id}` with `status: "open"` (Reopen in the UI) keeps the old `clinician_notes`; fine for now.
- **Anna**: `ChatMessageOut.citations[].section` is what the UI shows as a chip; keep it populated. Consider streaming later; the UI currently awaits the full reply.
- **Anna**: risk factor names shown to humans are mapped in `FACTOR_LABEL` (`src/lib/format.ts`); if the XGBoost model emits new feature names, tell Jacob or add labels there.
- **Team doc**: the GitHub link in the shared doc points to a ChatGPT page; fix it. Export the architecture diagram as PNG into the repo.

## Status log (newest first)

- 2026-11-07 15:45 — **Orchestrator visual QA passed** in the built-in browser against the live backend (dev server on :3000, backend on :8000, SQLite). Verified: landing at 1440 and 375 px (no horizontal overflow, phone conversation loops, both CTAs open and Esc closes; demo chat cites "Wound care" and marks "Can I eat sushi?" as sent to the care team; voice shows the not-configured state); signed-out `/patient/dashboard` redirects to `/login`; patient login → real care plan + chat history; check-in pain 9 + shortness of breath → High risk 60 %, care team alerted; live chat "Can I eat sushi?" → escalated; clinician login → both escalations in the queue with correct severity, acknowledge works with toast, all four drawer tabs load; after `6467cf3` the patients table has no inner scrollbar at 1280/1440 and both dialogs are 36rem. Zero console errors on every page. Screenshots committed to `frontend/docs/screenshots/` (12 JPGs). **Open items for Jacob**: ElevenLabs `onboard connect` + agent id (see "ElevenLabs setup"); Supabase project if the team still wants Supabase login; push `jacob/frontend` and open a PR into `main` when ready. `frontend/.env.local` exists locally (copied from the example, gitignored).

- 2026-11-07 — `6467cf3` layout fixes after orchestrator QA: clinician grid now 5/7 (queue/patients) at xl with a non-wrapping, truncating patients table (no inner scrollbar at ≥1280 px); "Text Foggy" and "Talk to Foggy" dialogs share a 36rem max width. Build + lint clean.

- 2026-11-07 — **Frontend built by Opus on `jacob/frontend`** (commits `52d5152` landing, `4aadd5b` login/auth, `3ea45ad` patient dashboard, `30af726` clinician dashboard, `95f6099` polish; not pushed; `CLAUDE.md` itself is still untracked and was not committed). `npm run build` and `npm run lint` pass with zero errors/warnings; all 5 routes prerender as static shells (client components fetch the API). A read-only node script confirmed every `lib/api/types.ts` shape matches the live backend (plus OpenAPI for SymptomOut/EscalationOut) and CORS returns `http://localhost:3000`.
  - **Exists**: `/` (Poke-style centered phone with auto-advancing, looping scripted Foggy chat + pause button; "Try texting Foggy" opens the shared `ChatPanel` in demo mode answering locally from `lib/demo/demoCarePlan.ts` with the backend's keyword + red-flag rules; "Talk to Foggy" voice modal; how it works, ethical-AI promise, audiences, closing CTA, footer with powered-by-JAB image and tracks). `/login` (Doctor/Patient toggle, prefilled demo creds, role-mismatch error, redirect by role). `/patient/dashboard` (greeting + day N + 6-week progress, reminders, check-in with risk result and "care team alerted", live Foggy chat with citation chips and "Sent to your care team", care plan sections, voice). `/clinician/dashboard` (stats, escalation queue polling every 5 s with toast + flash for new items, acknowledge/resolve-with-note/reopen, Active/Resolved/All, patient table, patient drawer with profile, risk factors, unanswered questions, check-ins, transcript, care plan upload with template).
  - **Mocked**: medications + appointments (`src/lib/api/reminders.ts`, "mark taken" persists to localStorage `cloudcare.mock.medlogs`), pending Barbara's routes. Supabase provider is scaffolded but dormant (no project; clear error if selected without env vars). Voice needs `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` (see "ElevenLabs setup").
  - **Known gaps**: no screenshots in `frontend/docs/screenshots/` yet (builder was told not to open a browser); clinicians cannot view the current care plan (backend ask); no visual QA done by the builder.
  - **Orchestrator verify**: from `frontend/`: `$env:PATH = "C:\Program Files\nodejs;$env:PATH"; npm run build; npm run lint; npm run dev`, then with the backend on :8000: (1) `/` at desktop and 375 px: phone conversation advances and loops, no horizontal scroll, both CTAs open dialogs, Esc closes, Tab order sensible; (2) `/login` → Patient → `/patient/dashboard` loads Jordan Lee, day 3, 5 care plan sections; send "When can I shower?" (Wound care chip) and "Can I eat sushi?" (Sent to your care team); check in with pain 9 + shortness of breath → High risk + care team alerted; (3) log out, `/login` → Doctor → `/clinician/dashboard`: the new escalations appear within 5 s (toast), acknowledge/resolve works, open Jordan's drawer tabs; (4) visiting a dashboard signed out redirects to `/login`; (5) save screenshots to `frontend/docs/screenshots/`.

- 2026-11-07 14:55 — Backend verified by orchestrator: `GET /health` → `{status: ok, database: sqlite}`; `POST /auth/login` for patient@demo.com returns Jordan Lee / patient; `GET /patients/me/care-plan` returns 5 chunks; `POST /chat` "When can I shower?" returns a grounded answer citing section "Wound care". Backend is running on http://localhost:8000 during the build (started by the orchestrator from the session's `.claude/launch.json`; SQLite file lands in the process cwd). `npm install` finished for `frontend/`. Opus builder launched.

- 2026-11-07 14:50 — Node 26 LTS installed via winget. Branch `jacob/frontend` fast-forwarded to origin/main (backend merged). `.venv` created (Python 3.14), backend requirements installing. Logos cropped into `frontend/public/brand/`. `npm install` running. Next: Opus builds the frontend per this file; orchestrator verifies build, lint, and screenshots against a running backend.
- 2026-11-07 — Repo at `9ed72c8`. Frontend is the untouched create-next-app scaffold. Backend has working auth + routes with SQLite fallback and seeded demo users. `ml/` empty. README empty.
