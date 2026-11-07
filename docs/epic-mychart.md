# Epic MyChart connection (SMART on FHIR)

Patients can link their MyChart account so CloudCare can read their medications, lab
results, visits and clinical notes from Epic, read-only, without uploads. This is a
patient-facing **SMART on FHIR standalone launch** (OAuth 2.0 authorization code + PKCE).
Clinician-side Epic workflows and MyChart messaging are out of scope.

## How the flow works

```
Dashboard ──fetch POST /api/auth/epic (Bearer)──▶ Next.js route ──▶ FastAPI POST /epic/connect/start
   │                                                                   (state + PKCE verifier saved, 10 min, single use)
   │◀──────────────────────── { authorize_url } ◀─────────────────────────┘
   └─ window.location.assign(authorize_url) ──▶ Epic / MyChart sign-in + consent
                                                        │
Epic ──302 /api/auth/callback/epic?code&state──▶ Next.js route ──▶ FastAPI POST /epic/connect/callback
                                                                     (state checked + deleted, code exchanged,
                                                                      tokens Fernet-encrypted into epic_connections)
Browser ◀──303 /patient/dashboard?epic=connected (+ HttpOnly cloudcare_epic cookie, UX only)
Dashboard ──Bearer──▶ FastAPI GET /epic/status, GET /epic/records, DELETE /epic/connection
```

The redirect URI has to live on the public site (Vercel), but the patient's CloudCare
session is a bearer token in localStorage that a browser navigation can't carry. So the
start call is a `fetch` with the token, and the callback is identified by the single-use
`state` alone. Tokens never reach the browser.

Code: `backend/app/epic/` (config, crypto, oauth, store, fhir, normalize, router),
`backend/app/models/epic.py`, `database/epic.sql`,
`frontend/src/app/api/auth/epic/route.ts`, `frontend/src/app/api/auth/callback/epic/route.ts`,
`frontend/src/lib/api/epic.ts`, `frontend/src/components/patient/MyChartCard.tsx`,
`frontend/src/components/patient/MyChartRecords.tsx`.

## 1. Register the app on fhir.epic.com

Sign in at https://fhir.epic.com → **Build Apps** → **Create**.

| Field | Value |
|---|---|
| Application Name | CloudCare |
| Application Audience | **Patients** |
| Incoming APIs | the list below |
| Redirect URIs | `https://cloudcare.icu/api/auth/callback/epic` and `http://localhost:3000/api/auth/callback/epic` (exact strings, no trailing slash) |
| SMART on FHIR Version | R4 |
| SMART Scope Version | SMART v1 (the default scopes in `EPIC_SCOPES` use `patient/<Resource>.read`) |
| Is Confidential Client | Off for a PKCE-only public client (default). Turn on only if you want refresh tokens (see "Refresh tokens") |
| Summary / description | Post-operative recovery companion; reads medications, labs, visits and notes to personalize recovery guidance |

Incoming APIs to select (names as Epic lists them):

| API | FHIR version | Used for |
|---|---|---|
| MedicationRequest.Read (Orders) | R4 | medications |
| MedicationRequest.Search (Orders) | R4 | medications |
| Medication.Read | R4 | resolving `medicationReference` |
| Medication.Search | R4 | (pairs with the above) |
| Observation.Read (Labs) | **STU3** | labs |
| Observation.Search (Labs) | **STU3** | labs (`category=laboratory`) |
| Encounter.Read (Patient Chart) | R4 | visits |
| Encounter.Search (Patient Chart) | R4 | visits |
| DocumentReference.Read (Clinical Notes) | R4 | notes |
| DocumentReference.Search (Clinical Notes) | R4 | notes (`category=clinical-note`) |
| Binary.Read (Clinical Notes) | R4 | note text previews (optional; without it notes show metadata only) |
| Observation.Search (Labs) | R4 | optional fallback when STU3 labs are unavailable |

Save, then copy the **Non-Production Client ID** into `EPIC_CLIENT_ID`. Epic's sandbox
requires the non-production id. New or edited apps can take a while to sync to the
sandbox; if the first sign-in says the client is unknown, wait and retry.

`aud` is set automatically to `EPIC_FHIR_BASE_URL` (the R4 base). The same token is used
for the STU3 labs endpoint; if the sandbox rejects that, labs fall back to the R4
Observation search and otherwise show as unavailable (nothing else breaks).

### Refresh tokens

Epic only issues refresh tokens to **confidential** clients (client secret or JWT
client authentication). A public PKCE client gets an access token (about an hour) and no
refresh token: when it expires, `/epic/records` answers 409 and the card shows
"Reconnect MyChart". For longer-lived access: tick **Is Confidential Client**, enable
refresh tokens in the app settings, put the secret in `EPIC_CLIENT_SECRET` (the API then
uses HTTP Basic client authentication), and add `offline_access` to `EPIC_SCOPES` if your
app settings ask for it. Epic's docs note that persistent patient access needs either a
BAA or telling the patient how long access lasts and getting consent.

## 2. Environment variables

### Backend (Render, and `backend/.env` locally)

| Name | What it is |
|---|---|
| `EPIC_CLIENT_ID` | Epic app client id (Non-Production for the sandbox). Required; without it `/epic/*` returns 503. |
| `EPIC_CLIENT_SECRET` | Client secret, only for a confidential client. Leave empty for PKCE-only. |
| `EPIC_FHIR_BASE_URL` | R4 FHIR base; also sent as `aud`. Sandbox default `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4`. |
| `EPIC_STU3_BASE_URL` | STU3 base used for labs. Defaults to the R4 base with `/R4` replaced by `/STU3`. |
| `EPIC_LABS_FHIR_VERSION` | `STU3` (default) or `R4`: which base labs are searched on first. |
| `EPIC_REDIRECT_URI` | Registered redirect URI for this environment (prod `https://cloudcare.icu/api/auth/callback/epic`, local `http://localhost:3000/api/auth/callback/epic`). |
| `EPIC_SCOPES` | Space-separated scopes; empty = `openid fhirUser` + `patient/{MedicationRequest,Medication,Observation,Encounter,DocumentReference}.read`. |
| `EPIC_TOKEN_ENCRYPTION_KEY` | Fernet key that encrypts stored tokens. Required; without it (or if invalid) `/epic/*` returns 503. |
| `EPIC_SANDBOX` | `true` while using Epic's sandbox; shows the sandbox note in the UI. |

Generate the encryption key once per environment and keep it stable (changing it makes
existing connections unreadable; those patients just reconnect):

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Frontend (Vercel, and `frontend/.env.local` locally)

| Name | What it is |
|---|---|
| `CLOUDCARE_API_URL` | Server-only FastAPI URL the two route handlers call. Falls back to `NEXT_PUBLIC_API_URL`. |
| `NEXT_PUBLIC_API_URL` | Already set; the dashboard calls `/epic/status`, `/epic/records`, `/epic/connection` here. |

## 3. Deploy

1. **Database** (Supabase SQL editor or psql, once): run `database/epic.sql`. It creates
   `epic_oauth_states` and `epic_connections`, enables RLS and revokes `anon` /
   `authenticated` access like `supabase_rls.sql`. Local SQLite creates the tables on
   startup. (On a plain Postgres without Supabase's roles, drop the `revoke` line.)
2. **Render** → cloudcare-api → Environment: set `EPIC_CLIENT_ID`,
   `EPIC_TOKEN_ENCRYPTION_KEY` (and `EPIC_CLIENT_SECRET` if confidential). The Blueprint
   already sets `EPIC_FHIR_BASE_URL`, `EPIC_STU3_BASE_URL`,
   `EPIC_REDIRECT_URI=https://cloudcare.icu/api/auth/callback/epic`, `EPIC_SANDBOX=true`.
   Save → Manual Deploy.
3. **Vercel** → Project → Settings → Environment Variables: add
   `CLOUDCARE_API_URL=https://cloudcare-api-q4zg.onrender.com` (Production + Preview),
   redeploy. Preview deployments have their own hostnames, which are not registered
   redirect URIs, so test the Epic flow on production or locally.
4. Render's free tier sleeps; the callback route waits up to 60 s for the API, but
   opening the dashboard first (which wakes the API) makes the round trip smoother.

## 4. Sandbox test, step by step

Local: backend on :8000 with the Epic env vars in `backend/.env`, frontend on :3000 with
`CLOUDCARE_API_URL=http://localhost:8000` (or just `NEXT_PUBLIC_API_URL`).

1. Sign in to CloudCare as a patient (`patient@demo.com` / `demo123`) → `/patient/dashboard`.
2. Scroll to **MyChart records**: it explains what is shared, shows **Connect MyChart**
   and the sandbox note. (Without `EPIC_CLIENT_ID` / key it says "MyChart connection
   isn't configured yet" instead.)
3. Click **Connect MyChart** → the button shows "Opening MyChart…" → the browser goes to
   `fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize?...` → Epic's sandbox MyChart
   login page.
4. Sign in as a sandbox MyChart test patient. Epic's sandbox lists these MyChart users:
   **Camila Lopez, Derrick Lin, Desiree Powell, Olivia Roberts**. Commonly published
   logins are `fhircamila` / `epicepic1` and `fhirderrick` / `epicepic1`; the current list
   is at https://fhir.epic.com/Documentation?docId=testpatients (see "What was verified").
   If one login is rejected, try another test patient.
5. Epic shows the consent screen listing the requested data → **Allow**.
6. You land on `/patient/dashboard`, a "MyChart connected" toast appears, the query string
   is cleaned, the card shows **Connected**, health system "Epic sandbox", today's date,
   and the Medications / Labs / Visits / Notes tabs fill in (counts on each tab). Tabs a
   test patient has no data for say "No … on file"; APIs the app wasn't granted say
   "Your health system hasn't shared … with CloudCare".
7. **Refresh records** refetches live; "Last synced" updates.
8. **Disconnect** → **Yes, disconnect** → toast, card returns to "Connect MyChart".
   `GET /epic/records` now answers 404 `MyChart is not connected`.
9. Check the API logs: only `epic.*` event names, status codes and counts; no tokens,
   codes, FHIR ids, names or payloads.

Quick API checks (patient bearer token in `$T`):

```
curl -H "Authorization: Bearer $T" http://localhost:8000/epic/status
curl -H "Authorization: Bearer $T" http://localhost:8000/epic/records
curl -X DELETE -H "Authorization: Bearer $T" http://localhost:8000/epic/connection
```

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Epic page says the redirect URI is invalid / doesn't match | `EPIC_REDIRECT_URI` differs from a registered URI (scheme, host, port, path, trailing slash), or you're on a Vercel preview host | Make `EPIC_REDIRECT_URI` exactly one of the registered URIs; use prod or localhost; wait for the app change to sync to the sandbox |
| Epic error about `aud` / invalid audience | `EPIC_FHIR_BASE_URL` isn't the FHIR base of the server you're authorizing against (e.g. trailing path, STU3 base, wrong environment) | Use the R4 base `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4` for the sandbox; no trailing slash needed |
| Dashboard toast "That sign-in link was already used or isn't valid" (`reason=invalid_state`) | State reused (back button, refresh of the callback URL, double click), started on a different API instance/database, or the user started a new attempt in another tab | Click Connect MyChart again; make sure the frontend's `CLOUDCARE_API_URL` points at the same API the dashboard uses |
| "The sign-in took longer than 10 minutes" (`reason=expired_state`) | More than 10 minutes between Connect and the callback | Start again |
| `reason=iss_mismatch` | `EPIC_FHIR_BASE_URL` changed between start and callback, or the redirect carried a different `iss` | Keep the base stable; restart the flow |
| `reason=token_exchange_failed` | Code expired or reused, wrong client id for this environment, confidential client without `EPIC_CLIENT_SECRET` (or the reverse) | Check `EPIC_CLIENT_ID` (Non-Production for sandbox) and secret settings; retry |
| `reason=no_patient` | The app's audience isn't **Patients**, so Epic didn't return `patient` | Set Application Audience to Patients |
| A tab says "hasn't shared … with CloudCare" (403) | That API isn't selected on the app, or the patient unchecked it on the consent screen | Add the API on fhir.epic.com (labs are **STU3**), wait for sync, reconnect |
| Card says "Needs reconnecting"; `/epic/records` returns 409 | Access token expired (public clients get no refresh token) or the patient revoked access in MyChart; a 401 after one refresh attempt marks the connection revoked | Click Reconnect MyChart; for longer access use a confidential client with refresh tokens |
| Card says "MyChart connection isn't configured yet" | API missing `EPIC_CLIENT_ID` or a valid `EPIC_TOKEN_ENCRYPTION_KEY` (503) | Set both on the API and redeploy |
| `reason=server_unreachable` | The Next.js route couldn't reach FastAPI (sleeping Render instance, wrong `CLOUDCARE_API_URL`) | Check `CLOUDCARE_API_URL`; open the dashboard first to wake the API |
| All connections broke after a deploy | `EPIC_TOKEN_ENCRYPTION_KEY` changed | Restore the old key, or have patients reconnect |

## 6. Security notes

- Tokens (and the PKCE verifier) are Fernet-encrypted at rest; plaintext exists only in
  memory during a request. Clinical data is fetched live and never stored.
- `state` is 256-bit random, bound to the CloudCare user, single use (atomic
  `DELETE ... RETURNING`), and expires after 10 minutes.
- PKCE S256 on every authorize request; `aud` pinned to the configured R4 base; the
  callback rejects a different `iss`; token responses without `patient`, or granting
  `user/` or `system/` scopes, are rejected.
- Paging only follows `Bundle.link[next]` URLs under the configured FHIR bases, so the
  bearer token is never sent elsewhere.
- Every `/epic/*` route except the callback resolves the connection by the signed-in
  user's id; patients can't see each other's connections.
- Note text is reduced to plain text on the API and rendered as text (no HTML injection).
- The `cloudcare_epic` cookie is HttpOnly, SameSite=Lax, 10 minutes, and only says
  "connected". The callback redirect sends `Referrer-Policy: no-referrer`.
- Logs carry event names, status codes and counts only.
- Disconnect deletes the row. Epic's sandbox SMART configuration advertises no
  revocation endpoint; if a production Epic instance does, the API calls it best effort.
  Patients can also revoke access from MyChart itself.

## 7. Tests

No Epic account needed: Epic is an `httpx.MockTransport`, the database in-memory SQLite.

```
.venv\Scripts\python.exe backend\tests\test_epic_oauth.py
.venv\Scripts\python.exe backend\tests\test_epic_fhir.py
```

They cover the authorize URL (PKCE S256, `aud`, `state`, scopes), unknown / expired /
reused state, `iss` mismatch, encrypted token storage that decrypts back, public vs
confidential token requests, refresh on 401 then revoked on a second 401, expired tokens,
normalization of R4 and STU3 shapes, `missing` flags on 403/404, STU3 → R4 lab fallback,
paging limits, patient isolation, disconnect, 503 when not configured, and that logs
contain no tokens, codes or ids.

## What was verified against Epic (November 2026)

Confirmed from Epic's live endpoints and docs:

- `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/.well-known/smart-configuration`:
  `authorization_endpoint` `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize`,
  `token_endpoint` `https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token`,
  `code_challenge_methods_supported` = S256 only, response type `code`, grant types include
  `authorization_code` and `refresh_token`, token auth methods `client_secret_post`,
  `client_secret_basic`, `private_key_jwt`; capabilities include `launch-standalone`,
  `client-public`, `client-confidential-symmetric`, `permission-offline`,
  `permission-patient`, `permission-v1`, `permission-v2`, `sso-openid-connect`.
  **No `revocation_endpoint`.** `scopes_supported` lists `openid`, `profile`, `fhirUser`,
  `launch` and an Epic scanning scope (resource scopes are governed by the app's API list).
- OAuth 2.0 docs (fhir.epic.com Documentation, oauth2): `response_type=code`, `client_id`,
  `redirect_uri` required; `state` recommended; `scope` required for the sandbox
  (`openid` alone suffices); `aud` is the FHIR base and is required from the May 2023
  Epic version; PKCE `code_challenge` with S256 only. Non-confidential token request:
  `grant_type`, `code`, `redirect_uri`, `client_id`, `code_verifier`. Token response:
  `access_token`, `token_type` bearer, `expires_in`, `scope`, `state`, `id_token` when
  `openid` was requested, `patient` for patient-facing launches. Refresh tokens are issued
  to confidential clients (client secret or JWT), not in non-confidential standalone
  responses; refresh uses `grant_type=refresh_token` with HTTP Basic or JWT client auth.
  Sandbox requires the non-production client id. Sandbox bases `.../api/FHIR/R4/`,
  `.../api/FHIR/STU3/`, `.../api/FHIR/DSTU2/`.
- API names for patient-facing apps (USCDI list): MedicationRequest.Read/Search (Orders)
  (R4), Medication.Read/Search (R4), Observation.Read/Search (Labs) (**STU3**),
  Encounter.Read/Search (Patient Chart) (R4), DocumentReference.Read/Search (Clinical Notes) (R4).
- R4 CapabilityStatement (`.../FHIR/R4/metadata`): MedicationRequest search supports
  `patient`, `status`, `category`, `_count`; Medication read/search (`_id`); Observation
  search supports `patient`, `category`, `code`, `date`; Encounter `patient`, `date`,
  `class`; DocumentReference `patient`, `category`, `type`, `date`; Binary read. No
  revoke/manage OAuth URIs. STU3 CapabilityStatement: Observation search supports
  `patient` and `category` (laboratory among the listed categories).

Could not be confirmed from Epic directly (the pages render client-side and the fetched
text did not include them), so the code keeps them configurable or tolerant:

- The sandbox MyChart test-patient credentials page. The sandbox login page names the
  MyChart users above; the `fhircamila` / `fhirderrick` + `epicepic1` logins come from
  widely used third-party guides, and one public report (Oct 2025) says `fhircamila`
  stopped working for a while. Check the testpatients page in a browser.
- The individual API specification pages (exact parameter requirements, patient-facing
  notes, whether `offline_access` is honored for patient apps, the exact Binary API name
  for clinical note content, whether the R4 token is accepted on the STU3 endpoint).
  Hence: `EPIC_SCOPES` is configurable and excludes `offline_access` by default; labs try
  STU3 then fall back to R4 (`EPIC_LABS_FHIR_VERSION`), and a 401 from the STU3 endpoint
  is treated as "labs unavailable" rather than a revoked connection; a 403/404 on any one
  resource only marks that resource `missing`; note bodies are optional.
