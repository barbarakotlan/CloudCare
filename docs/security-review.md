# CloudCare security review

Date: 2026-11-08. Scope: code review of `backend/**` and `frontend/**`; active testing against local
instances only (Next.js on `localhost:3000`, an isolated SQLite copy of the API on `localhost:8020`);
passive checks only (response headers, TLS, exposed files) against `https://cloudcare.icu` and
`https://cloudcare-api-q4zg.onrender.com`. No third-party service (Supabase, ElevenLabs, Twilio, Epic,
Google) was attacked; the Supabase check was a single read-only catalog query.

Severity: **High** = cross-account data access or abuse of a real person; **Medium** = exploitable
weakness with limited impact or a precondition; **Low** = hardening; **Info** = verified safe.

## Findings

| ID | Severity | Area | Finding | Status | Evidence |
|---|---|---|---|---|---|
| K-01 | High | Epic | MyChart connect was not bound to the browser that started it. An attacker could start `POST /api/auth/epic` on their own CloudCare account, send the resulting Epic sign-in link to a victim, and once the victim signed in to MyChart the victim's medications, labs, visits and notes would be attached to the attacker's account. | Fixed | `POST /api/auth/epic` now sets an HttpOnly, SameSite=Lax, path-scoped `cloudcare_epic_state` cookie holding the OAuth `state` (10 min). The callback refuses (`reason=state_mismatch`) unless the cookie matches, and clears it. Local probe: callback without the cookie → `303 /patient/dashboard?epic=error&reason=state_mismatch`, no backend call. `frontend/src/lib/server/epicState.ts`. |
| K-02 | High | Outreach | The shared demo patient login is public. Anyone could sign in as it, save a stranger's number with `PATCH /patients/me` and press "Call me" or "Text me", so CloudCare would phone or text that person (harassment, cost). Real accounts could cycle numbers the same way. | Mitigations built; the two strongest are **opt-in and off by default** (owner decision for the live demo, where attendees type in their own numbers) | Opt-in: `OUTREACH_DEMO_ALLOWLIST` set to a list restricts demo accounts (`@demo.com`) to those numbers, `none` blocks them, unset or `*` (default) allows any usable number; `GET /outreach/capabilities` reports `call:false`/`sms:false` with reason "Demo accounts can only call approved test numbers" when restricted. `OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS` (default 0; 600 recommended for a hardened deployment) blocks texts/calls for that long after a number is set (sign-up, profile edit, clinician edit). Always on: at most 6 texts and 6 calls per destination number per day across all accounts, 40 per patient per channel per day, 30 calls per hour server-wide; numbers listed explicitly in the allowlist (the team's own phones) skip the cooldown and daily caps. `/demo/reset` no longer releases the call interval. **Turn the cooldown on and set the allowlist after the demo.** Tests: `test_security.py` (`test_demo_account_only_reaches_allowlisted_numbers`, `test_new_number_cooldown_blocks_calls_and_texts`, `test_per_patient_and_per_number_daily_caps`, `test_demo_reset_does_not_release_call_interval`, `test_signup_number_starts_the_cooldown`). |
| K-03 | Medium | Auth | If `JWT_SECRET` were missing on a deploy, the API silently used the dev default from the repo, so anyone could forge a clinician token. | Fixed | In production (`RENDER` set, or `ENV`/`APP_ENV`=production) a missing, default or <32-character secret turns CloudCare's own HS256 tokens off: such tokens are rejected (401), `POST /auth/login` answers 503, phone calls answer "not set up". Supabase sign-in is unaffected. Render uses `generateValue: true`, so the live API should be fine; the value itself was not inspected. `test_dev_secret_forgery_rejected_in_production`. |
| K-04 | Medium | Abuse | No request rate limits: password guessing and scrypt CPU on `/auth/login`, language-model cost on `/chat`, and spam on `/symptoms`, care-plan upload, Epic start and `/demo/reset`. | Fixed | `/auth/login`: 10 failures per (address, email) per 15 min, 60 attempts per address per 15 min, 429 + Retry-After. Per account: `/chat` 30/min, `POST /symptoms` 20/min, care-plan upload 30/min, Epic start 10/min, demo reset 5/min. Live probe on :8020: 12 bad logins → 10×401 then 429. `app/security.py`, `app/rate_limits.py`. |
| K-05 | Medium | Outreach / Auth | The 30-minute token handed to the voice provider for each phone call was a full patient session (could read the profile, change the phone number, start more calls). | Fixed | Tokens with `purpose: phone_call` are accepted only on `/chat` and `/chat/*`; any other route answers 401. `test_phone_call_token_only_opens_chat`. |
| K-06 | Medium | Input validation | No request body limit; unbounded `title`/`raw_text` (care plan), `free_text` (check-in), `clinician_notes`, `comorbidities`, and login `password` (fed to scrypt). | Fixed | 256 KB body limit (Content-Length and streamed bodies) → 413; care plan title ≤ 200, text ≤ 50,000; `free_text` ≤ 2,000; notes ≤ 4,000; comorbidities ≤ 50 × 100 chars; login email ≤ 320, password ≤ 256. `ChatIn.message` ≤ 2,000 was already in place. Live probe: 400 KB body → 413 (with and without Content-Length). |
| K-07 | Medium | Frontend headers | `cloudcare.icu` sent no Content-Security-Policy, X-Frame-Options/frame-ancestors, X-Content-Type-Options, Referrer-Policy or Permissions-Policy (only Vercel's HSTS). | Fixed (ships with the next Vercel build) | `frontend/next.config.ts` `headers()`: CSP (below), HSTS 2 years + subdomains, nosniff, `X-Frame-Options: DENY` + `frame-ancestors 'none'`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: microphone=(self), camera=(), geolocation=(), payment=(), usb=()`, `X-Powered-By` removed. Verified on the dev server: landing, login and patient dashboard load with no CSP violations; in-page check shows `api.elevenlabs.io` allowed, `example.com` blocked, AudioWorklet from a blob: URL loads. |
| K-08 | Low | CORS | API allowed credentials with `*` methods/headers although the app never sends cookies to it. | Fixed | `allow_credentials=False`, methods and headers listed explicitly, 10-min preflight cache. Origins stay `CORS_ORIGINS` (default localhost:3000, cloudcare.icu, www). Live Render (before deploy): preflight from cloudcare.icu returned `Access-Control-Allow-Credentials: true`; from `evil.example` 400 with no ACAO. |
| K-09 | Low | Epic | The callback built its redirect from the request's Host header (absolute URL). Not an open redirect (path fixed, `reason` whitelisted), but depended on the proxy's Host handling. | Fixed | Relative `Location: /patient/dashboard?...`. Probe with `Host: evil.example` → relative location. `?reason=https://evil.example` → collapsed to `epic_error`. |
| K-10 | Low | Logging | Auth logs included patient email addresses; one log line included the token library's exception text. | Fixed | Logs carry user ids and exception type names only. A scan of the :8020 server log after all probes found no `Bearer`, `eyJ`, `@` or passwords. |
| K-11 | Low | Auth | Login skipped scrypt for unknown emails, a timing signal for which emails have accounts. | Fixed | A dummy hash is checked instead; both paths return the same 401 body. |
| K-12 | Low | Auth | A locally signed token without `exp` would have been accepted forever. | Fixed | `exp` and `sub` required. `test_local_token_needs_exp_and_rejects_expired`. |
| K-13 | Low | Errors | Unhandled exceptions return Starlette's plain "Internal Server Error" (no stack trace, already safe). | Fixed (hardening) | JSON 500 handler with a fixed message; details go to the log only. `test_unhandled_errors_hide_details` raises an exception containing `sb_secret_...` and checks it never reaches the client. |
| K-14 | Low | API headers | API responses had no nosniff/frame/referrer headers, and authenticated JSON could be cached by intermediaries. | Fixed | `SecurityHeadersMiddleware`: nosniff, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-site`, `Cache-Control: no-store` on any request with Authorization, HSTS in production. |
| K-15 | Info | Auth | JWT algorithm confusion. | Verified safe | The header only routes a token: `HS256` → local verifier pinned to HS256 with `JWT_SECRET`; anything else → Supabase verifier pinned to ES256/RS256 with keys from the project JWKS, `aud=authenticated`, `iss=<project>/auth/v1`, `exp/sub/aud/iss` required. Tested: `alg: none` (any casing), HS256 signed with the published EC public key, ES256 header on an HS256 signature, expired, wrong audience/issuer, unknown `kid`, anonymous sessions → all 401. Role comes from `app_metadata` only. |
| K-16 | Info | Authorization | Cross-patient and cross-clinician access (IDOR). | Verified safe | Patient A vs patient B: clinician routes 403; `?patient_id=` ignored for patients on `/symptoms` and `/chat/history`; B's medication log → 404. Dr. Patel vs unassigned/other clinician's patient: `/patients/{id}`, care plan GET/POST, profile PATCH, `/symptoms?patient_id`, `/chat/history?patient_id`, `PATCH /escalations/{id}` → 404; lists exclude them. Demo clinician cannot list or claim unassigned sign-ups (403). `/epic/*` and `/outreach/*` resolve by the signed-in user only. `/demo/reset` limited to clinicians and demo patients. `test_patient_cannot_read_another_patient`, `test_clinician_limited_to_assigned_patients`. |
| K-17 | Info | Epic | State, PKCE, iss, token storage. | Verified safe (one note) | State is 32 random bytes, single use (atomic `DELETE ... RETURNING`), 10-minute expiry, one pending state per user; PKCE S256; `iss` and redirect URI checked; tokens Fernet-encrypted; scopes checked; tokens never reach the browser; `POST /api/auth/epic` requires the bearer token and now also refuses a foreign `Origin`. Note: dev machines and Render share one `EPIC_TOKEN_ENCRYPTION_KEY` because they share one database (see Deferred). |
| K-18 | Low | Frontend | The CloudCare bearer token (`cloudcare.token`) and the Supabase session (including its refresh token) live in `localStorage`, readable by any script that runs on the origin. | Accepted | Trade-off: the API is a separate origin (Render) and the token must ride in `Authorization`. Mitigations: CSP limits script sources to the site itself and blocks connections to unknown hosts (stolen tokens can't be posted to an arbitrary server with fetch/XHR/WebSocket); no `dangerouslySetInnerHTML`, `innerHTML`, `eval` or `new Function` anywhere in `frontend/src` (grep); React escapes all text; Epic notes are rendered as plain text; tokens expire (12 h local, 1 h Supabase access). Longer-term: an HttpOnly cookie session through Next.js route handlers. |
| K-19 | Low | Frontend | CSP allows `'unsafe-inline'` scripts. | Accepted | Pages are static shells (`cacheComponents`), and Next.js inlines its bootstrap; nonces would force per-request rendering. Revisit with Next's hash-based SRI once it leaves experimental. |
| K-20 | Low | API | `/docs`, `/redoc` and `/openapi.json` are public on Render (route list and schemas, no data). | Accepted | Useful for the team; contains nothing secret. Could be turned off in production later. |
| K-21 | Low | Hosting | `https://www.cloudcare.icu` fails certificate validation ("Could not establish trust relationship"). | Deferred (dashboard, not code) | Add `www.cloudcare.icu` as a domain in the Vercel project (redirect to the apex). `http://cloudcare.icu` → 308 to HTTPS; TLS 1.1 refused, TLS 1.2 accepted on both hosts. |
| K-22 | Info | Database | SQL injection. | Verified safe | All queries use the SQLAlchemy ORM with bound parameters; filters are `Literal` enums, ids are UUID-typed, `since` is a parsed datetime. Probes (`?status=x'--`, `?since=1' or 1=1`, non-UUID paths) → 422. |
| K-23 | Info | Supabase | Row Level Security. | Verified safe | Read-only catalog query: all 15 public tables have RLS on, zero policies, and `anon`/`authenticated` have no select/insert/update/delete. No `SECURITY DEFINER` functions in `public`. The 118 `public` functions are pgvector's (executable by anon, harmless; Supabase's advisor suggests moving the extension to its own schema). |
| K-24 | Info | Dependencies | Known-vulnerable packages. | Verified safe | `npm audit --omit=dev`: 0 vulnerabilities. `pip-audit -r backend/requirements.txt`: no known vulnerabilities (all pins exact). |
| K-25 | Info | Secrets | Secrets in the browser bundle or git. | Verified safe | `.next/static` grep for `sb_secret`, `service_role`, `ELEVENLABS_API_KEY`, `LLM_API_KEY`, `TWILIO_AUTH`, `xi-api-key`: only supabase-js's own `startsWith("sb_secret_")` prefix check. Only `backend/.env.example` and `frontend/.env.local.example` are tracked; the one historical `backend/.env` commit was an empty file. `cloudcare.icu/.env`, `/.git/config`, `/package.json` → 404; source maps → 403. |
| K-26 | Low | Abuse | Rate limits, cooldowns and per-number caps are in memory: they reset on restart/deploy and aren't shared between processes. | Accepted | Render runs one process; a restart needs 15 idle minutes, longer than the 10-minute cooldown. The per-patient daily cap and call interval also read `outreach_log`. Move to a shared store if the API is ever scaled out. |
| K-27 | Low | Abuse | Anyone can create a patient account (Supabase sign-up). | Accepted | New accounts are unassigned, see nothing clinical, and a sign-up phone number starts the 10-minute cooldown. Relies on Supabase Auth's email confirmation and built-in sign-up rate limits; confirm "Confirm email" is on in the Supabase dashboard (not checked here). |
| K-28 | Low | Errors | FastAPI's 422 responses echo the rejected input back to the same client (for example an over-long password). | Accepted | Returned only to the sender; the API never logs request bodies. Clients must not log 422 bodies. |
| K-29 | Low | Auth | Behind Render's proxy the login limiter keys on the last `X-Forwarded-For` hop, which may be a shared edge address rather than the person. | Accepted | Worst case: password sign-in for one email is paused for 15 minutes for people on the same edge. Password sign-in is the fallback; the live site signs in through Supabase. |
| K-30 | Medium | Outreach | Any account can still have a number it doesn't own called after saving it (immediately while the cooldown is off, otherwise once the cooldown passes), within the daily caps. | Deferred | Proper fix: verify the number with a one-time code by text before the first call (needs Twilio texting, pending toll-free verification). |

## Content-Security-Policy (production)

```
default-src 'self';
script-src 'self' 'unsafe-inline' blob: https://cdn.jsdelivr.net/npm/@alexanderolsen/libsamplerate-js@2.1.2/;
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:;
font-src 'self' data:;
media-src 'self' blob: data:;
connect-src 'self' <NEXT_PUBLIC_API_URL origin> <NEXT_PUBLIC_SUPABASE_URL origin> <same, wss://>
            https://api.elevenlabs.io wss://api.elevenlabs.io https://*.elevenlabs.io wss://*.elevenlabs.io;
worker-src 'self' blob:;
frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self';
upgrade-insecure-requests
```

`next dev` adds `'unsafe-eval'` and `ws://localhost:*` (React debugging and hot reload). The API and
Supabase origins are read from `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_SUPABASE_URL` at build time, so a
new API host needs a rebuild. Voice: the ElevenLabs SDK fetches its token from `api.elevenlabs.io`,
connects to `wss://livekit.rtc.elevenlabs.io`, and loads audio worklets from `blob:` URLs (or the pinned
jsdelivr file when resampling). The MyChart popup is a navigation to Epic, which CSP doesn't govern; no
`Cross-Origin-Opener-Policy` is set, so the popup can still post its result to the dashboard.

**Not verified here:** a full spoken voice session (the review browser blocks the microphone, so the
session stopped at the permission prompt with no CSP errors) and a full MyChart round trip (it writes to
the shared Supabase database). Please do both once on `localhost:3000` or the Vercel preview before
merging: press "Talk to Foggy" → "Start talking", and Connect MyChart with the Epic test patient.

## Configuration

Backend (Render dashboard and `backend/.env`; documented in `backend/.env.example`):

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | HS256 signing key, at least 32 characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). In production, missing/default/short turns CloudCare's own tokens off. Render: `generateValue: true`. |
| `RENDER` / `ENV` / `APP_ENV` | Production detection. Render sets `RENDER` itself; set `ENV=production` on any other host. Also enables HSTS on API responses. |
| `OUTREACH_DEMO_ALLOWLIST` | Who the shared demo accounts may text or call. **Unset or `*` (default) = any usable number** (demo day). A comma-separated list of numbers (any format, stored as E.164) restricts them to those numbers; `none` blocks them. Listed numbers also skip the cooldown and daily caps. In `render.yaml` as `sync: false`. |
| `OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS` | Wait after a number is set or changed before texts/calls. **Default 0 (off)** so a live demo can call any number an attendee types in; set 600 for a hardened deployment. |
| `OUTREACH_MAX_PER_PATIENT_PER_DAY` | Texts and calls per patient per channel per 24 h (default 40). |
| `OUTREACH_MAX_PER_NUMBER_PER_DAY` | Texts and calls per destination number per channel per 24 h, across accounts (default 6). |
| `OUTREACH_MAX_CALLS_PER_HOUR` | Calls started per hour, whole server (default 30). |
| `CORS_ORIGINS` | Browser origins allowed to call the API (no credentials). |
| `EPIC_TOKEN_ENCRYPTION_KEY` | Fernet key for stored Epic tokens; the API refuses `/epic` (503) without a valid key. |
| `RESEND_API_KEY` | Server-only email provider key. Set: each stored onboarding request is also emailed to `SALES_LEAD_TO` (default `support@cloudcare.icu`) with reply-to the visitor's work email, and the `sales_emails` row records `sent` or `failed`; unset: stored only, no network call. `sync: false` in `render.yaml`. |
| `SALES_EMAIL_FROM` | Sender for those emails, on a domain verified with the provider (default `CloudCare <no-reply@cloudcare.icu>`). `sync: false` in `render.yaml`. |
| Server-only secrets | `SUPABASE_SERVICE_ROLE_KEY`, `LLM_API_KEY`, `ELEVENLABS_API_KEY`, `TWILIO_AUTH_TOKEN`, `EPIC_CLIENT_SECRET`, `DATABASE_URL`: Render only, never `NEXT_PUBLIC_*`. |

Frontend (Vercel): `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SUPABASE_URL` (also feed the CSP),
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_ELEVENLABS_AGENT_ID`, `NEXT_PUBLIC_AUTH_PROVIDER`
(public by design); `CLOUDCARE_API_URL` (server-only, used by the Epic route handlers).
`ELEVENLABS_API_KEY` in `frontend/.env.local` is for the ElevenLabs CLI only and must never be added
to Vercel.

## Deferred (needs a decision or another owner)

1. Verify phone numbers with a one-time text code before the first call (K-30).
2. Add `www.cloudcare.icu` to the Vercel project (K-21).
3. Separate Epic encryption keys per environment once local development stops sharing the production database (K-17).
4. HttpOnly cookie sessions instead of `localStorage` tokens (K-18); SRI-based CSP without `'unsafe-inline'` (K-19).
5. Move rate-limit state to the database or a cache if the API ever runs more than one process (K-26).
6. After the live demo: on Render set `OUTREACH_NEW_NUMBER_COOLDOWN_SECONDS=600` and `OUTREACH_DEMO_ALLOWLIST` to the team's phones (or `none`), then Manual Deploy. Until then the demo login can call any number an attendee enters, within the daily and hourly caps (K-02).

## How to re-run

```powershell
# from the repo root
.\.venv\Scripts\python.exe backend\tests\test_security.py     # 24 checks for this review
foreach ($f in Get-ChildItem backend\tests\test_*.py) { .\.venv\Scripts\python.exe $f.FullName }
cd frontend; npm audit --omit=dev
.\.venv\Scripts\python.exe -m pip_audit -r backend\requirements.txt
```
