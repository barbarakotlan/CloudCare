# ☁️ CloudCare

> **Your head's in the clouds. Your care shouldn't be.**

CloudCare is an AI-powered post-operative recovery companion. It brings the care team's instructions home, answers patients' questions **only** from what their clinician wrote, scores symptom check-ins with a machine-learning risk model, and escalates anything worrying to a human.

---

## The problem

Patients get critical recovery instructions right after surgery, while they're still foggy from anesthesia. Then they're expected to remember everything and recognize when something is wrong. Many don't, and complications get caught late.

## The solution

| For patients | For clinicians |
|---|---|
| **Foggy**, a chat (and voice) assistant that answers from *their* care plan and cites the section it used | A live **escalation queue**, sorted by urgency |
| Daily **symptom check-ins** that return a recovery risk score | A **patient list sorted by ML risk**, showing *why* each patient was flagged |
| Medication and appointment **reminders** | **Care plan upload**: paste instructions and Foggy uses them immediately |
| A clear "call 911 / call your surgeon" message when something sounds dangerous | Full chat transcripts and check-in history for each patient |

---

## Hackathon tracks

### 🤖 Ethical AI Agent
Foggy is designed so it **can't freelance medical advice**:
1. **Emergencies never depend on the AI.** Phrases like "chest pain" or "can't breathe" are caught by rules *before* the LLM runs, and the patient is told to call 911.
2. **It answers only from the clinician's care plan,** and cites the section it used.
3. **Every answer is fact-checked** against the cited text before the patient sees it. We found that a small local model can't reliably judge itself, so the check is rule-based: the question's topic must appear in the cited section, and the answer may not introduce numbers or claims that aren't in it.
4. **If the plan doesn't cover it, Foggy doesn't guess.** It says so, and the question goes to the care team.
5. **Humans close the loop.** Every escalation is reviewed, noted and resolved by a clinician.
6. **Graceful degradation.** If the LLM is down, Foggy falls back to quoting the care plan, and if the risk model is missing, scoring falls back to rules. The app never fails open.

### 📊 ML and Data Science
An **XGBoost** model predicts post-op complication risk from each check-in, and explains every score using per-feature SHAP contributions. See [Risk model](#risk-model).

### 🏥 Healthcare
It targets a real gap in post-operative care: the time between discharge and the first follow-up, when patients are alone with instructions they may not remember.

---

## How it works

```mermaid
flowchart TB
    subgraph Users
        P[Patient app<br/>chat · voice · check-ins]
        C[Clinician dashboard<br/>queue · patients · care plans]
    end
    P & C <--> API[FastAPI backend<br/>auth · routes]
    API --> F[Foggy<br/>ai_service.py]
    API --> R[Risk model<br/>ml_service.py]
    F --> RF{Red flag?}
    RF -- yes --> ESC[Escalation<br/>emergency]
    RF -- no --> LLM[Ollama LLM<br/>answers from care plan]
    LLM --> FC{Fact-check<br/>passes?}
    FC -- yes --> ANS[Answer + citation]
    FC -- no --> ESC2[Escalation<br/>unanswered question]
    R --> XGB[XGBoost + SHAP]
    XGB -- high risk --> ESC3[Escalation<br/>high risk]
    API <--> DB[(PostgreSQL / SQLite<br/>users · care plans · check-ins<br/>chat · risk scores · escalations)]
    ESC & ESC2 & ESC3 --> C
```

### Example flow
1. Dr. Patel uploads Jordan's knee-replacement instructions.
2. Jordan asks Foggy *"Can I take a shower?"* and gets an answer that cites **Wound care**.
3. Jordan asks *"Can I drink wine tonight?"*. That isn't in the plan, so Foggy says so and sends the question to Dr. Patel.
4. Jordan's check-in reports a fever of 101.9°F with wound drainage. The risk score is **0.99 (high)**, the top reasons are *fever, wound drainage, pain*, and an escalation is opened automatically.
5. Dr. Patel sees Jordan at the top of the queue, calls them, and resolves the escalation with a note.

---

## Foggy (AI assistant)

Code: [`backend/app/services/ai_service.py`](backend/app/services/ai_service.py)

- **Model:** runs locally with [Ollama](https://ollama.com) (default `llama3.2`, 3B parameters). No API key is needed, and patient questions never leave the machine.
- **Grounding:** the patient's care plan sections go into the prompt. The model must reply in a fixed JSON format (`answer`, `in_plan`, `source_ids`, `urgent`).
- **Safety pipeline:** red-flag rules, then the LLM, then a check that it cited a real section, then the rule-based fact-check, then the answer. Anything that fails a step is sent to a human.

**Evaluation** (12 questions with llama3.2, against the demo knee-replacement care plan):

| Type | Examples | Result |
|---|---|---|
| Answered by the plan | shower, driving, swelling, Tylenol | 4/4 answered correctly, with the right citation |
| Not in the plan | wine, side-sleeping, coffee, work, ibuprofen, stairs | 6/6 declined and sent to the care team |
| Urgent / emergency | fever 102.3 with leaking incision, chest pain | 2/2 escalated |

Before the fact-check was added, the model **made up answers** for the wine and side-sleeping questions ("no alcohol for 4 weeks"). The fact-check eliminated those.

---

## Risk model

Code: [`ml/`](ml/), served by [`backend/app/services/ml_service.py`](backend/app/services/ml_service.py)

> ⚠️ **The model is trained on synthetic data, not real patients.** The data is generated by [`ml/generate_data.py`](ml/generate_data.py) with realistic, noisy patterns (older age, diabetes, smoking, and fever / wound changes raise risk). Real-world accuracy would be lower.

- **Data:** 5,000 synthetic check-ins, 7.2% complication rate. The columns match the `symptom_logs` table exactly, so real check-ins can be scored directly.
- **Features:** age, procedure type, days since surgery, diabetes, smoking, obesity, pain, temperature, wound redness and drainage, swelling, nausea, shortness of breath, mobility.
- **Model:** XGBoost classifier (300 trees, depth 4).
- **Explainability:** every score includes its top 3 reasons, from XGBoost's per-feature SHAP contributions.

**Results** (on 1,000 held-out test rows):

| Metric | XGBoost | Hand-written rules baseline |
|---|---|---|
| ROC AUC | **0.974** | 0.939 |
| PR AUC | **0.862** | 0.709 (random = 0.072) |
| 5-fold CV ROC AUC | 0.963 ± 0.010 | |

**Risk levels:**
- **High** (score ≥ 0.20) escalates to the care team. It catches 85% of complications, and 70% of flags are real.
- **Medium** (score ≥ 0.07) means "keep an eye on it". Medium or above catches 90% of complications.

**Most important features:** wound drainage, temperature, pain, wound redness, shortness of breath. These are the same warning signs a clinician looks for.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4 |
| Voice | Browser speech, plus ElevenLabs Conversational AI for "Talk to Foggy" |
| Backend | Python, FastAPI, SQLAlchemy 2, PyJWT |
| Database | PostgreSQL with pgvector (schema in [`database/scheme.sql`](database/scheme.sql)). Falls back to SQLite for local development |
| LLM | Ollama (local), `llama3.2` by default |
| ML | XGBoost, scikit-learn, pandas, NumPy |

## Repository layout

```
CloudCare/
├── frontend/                 Next.js app (see frontend/README.md)
│   └── src/
│       ├── app/              routes: / · /login · /patient/dashboard · /clinician/dashboard
│       ├── components/       chat, patient, clinician, landing, voice, ui
│       └── lib/              api client, auth, demo data, hooks
├── backend/
│   └── app/
│       ├── main.py           FastAPI app, CORS, startup (tables + demo seed)
│       ├── database.py       DB connection (DATABASE_URL, else SQLite)
│       ├── auth.py           password hashing, JWT, role checks
│       ├── models/           SQLAlchemy models (one per table)
│       ├── schemas.py        API request/response shapes
│       ├── routes/           auth · patients · symptoms · chat · escalations
│       ├── services/
│       │   ├── ai_service.py Foggy: red flags → Ollama → fact-check
│       │   └── ml_service.py risk scoring (XGBoost, rules fallback)
│       └── seed.py           demo accounts, patient and care plan
├── ml/
│   ├── generate_data.py      synthetic dataset
│   ├── train.py              train + evaluate XGBoost
│   ├── predict.py            load model, score + explain one check-in
│   └── models/               trained model + metrics (risk_model_meta.json)
└── database/
    └── scheme.sql            PostgreSQL schema (11 tables)
```

---

## Getting started

### Prerequisites
- **Python 3.14+**
- **Node.js 20+**
- **[Ollama](https://ollama.com/download)**, for Foggy's LLM. Optional: without it, Foggy falls back to quoting the care plan.

### 1. Backend
```powershell
# from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd backend
copy .env.example .env        # optional: edit DATABASE_URL, JWT_SECRET, OLLAMA_MODEL
uvicorn app.main:app --reload
```
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- With no `DATABASE_URL`, it uses a local SQLite file (`backend/cloudcare.db`), creates the tables, and seeds the demo data automatically.

### 2. Foggy's LLM (optional but recommended)
```powershell
ollama pull llama3.2          # ~2 GB, one time
```
Keep Ollama running; it starts automatically on Windows. The first answer can take 10–30 seconds while the model loads.

### 3. Frontend
```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev                   # http://localhost:3000
```

### 4. Log in with a demo account
Both accounts use the password `demo123`.

| Role | Email | Who |
|---|---|---|
| Patient | `patient@demo.com` | Jordan Lee: total knee replacement 3 days ago, has diabetes |
| Clinician | `clinician@demo.com` | Dr. Priya Patel, Jordan's surgeon |

### Retrain the risk model (optional)
A trained model is already committed in `ml/models/`. To regenerate the data and retrain:
```powershell
python ml\generate_data.py    # → ml/data/synthetic_recovery.csv
python ml\train.py            # → ml/models/risk_model.json + metrics
python ml\predict.py          # quick sanity check on two example check-ins
```

### Use PostgreSQL instead of SQLite
Create a database (Supabase or Neon both work, and both include pgvector), run `database/scheme.sql` against it, and set `DATABASE_URL` in `backend/.env`.

---

## Configuration

**Backend** (`backend/.env`, template: [`backend/.env.example`](backend/.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local SQLite | e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `JWT_SECRET` | dev placeholder | Secret for signing login tokens. **Set this for any shared deployment** |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `llama3.2` | Any Ollama chat model, e.g. `qwen2.5:7b` for better rule-following |

**Frontend** (`frontend/.env.local`): see [`frontend/README.md`](frontend/README.md). The key variables are `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_ELEVENLABS_AGENT_ID`.

---

## API reference

Every route except `/auth/login` needs `Authorization: Bearer <token>`. Full interactive docs are at `/docs`.

| Method | Path | Who | Description |
|---|---|---|---|
| `POST` | `/auth/login` | anyone | Email + password → token and user role |
| `GET` | `/auth/me` | any | Current user |
| `GET` | `/patients` | clinician | Assigned patients with latest risk, open escalations and last check-in |
| `GET` | `/patients/me` | patient | Own profile |
| `GET` | `/patients/me/care-plan` | patient | Active care plan, split into sections |
| `GET` | `/patients/{id}` | clinician | One patient |
| `POST` | `/patients/{id}/care-plan` | clinician | Upload new instructions (replaces the active plan) |
| `POST` | `/symptoms` | patient | Check-in → risk score → escalation if high |
| `GET` | `/symptoms` | both | Check-in history (`?patient_id=` for clinicians) |
| `POST` | `/chat` | patient | Ask Foggy (escalates red flags and unanswered questions) |
| `GET` | `/chat/history` | both | Conversation (`?patient_id=` for clinicians) |
| `GET` | `/escalations` | clinician | Queue, most urgent first (`?status=active\|open\|acknowledged\|resolved\|all`) |
| `PATCH` | `/escalations/{id}` | clinician | Acknowledge or resolve, with notes |

---

## Status and roadmap

**Working end to end:** login, Foggy chat with fact-checking, symptom check-ins with XGBoost risk scores, automatic escalations, clinician queue, care plan upload, demo data.

**In progress:**
- Medication and appointment routes. The tables exist; the frontend shows sample reminders until the routes are added.
- Clinician read access to a patient's care plan.

**Future ideas:**
- Embedding-based retrieval (pgvector) for long care plans
- SMS and phone reminders (Twilio)
- Epic / MyChart integration via [FHIR](https://fhir.epic.com/)
- Production authentication

---

## Limitations and disclaimer

- **CloudCare is a hackathon prototype, not a medical device.** It is not intended for real clinical use.
- The risk model is trained on **synthetic data**, and its metrics would not hold on real patients without retraining and validation.
- Login uses demo accounts and a simple token system, not production-grade authentication.
- Foggy deliberately leans toward caution: unusual phrasings may be sent to the care team instead of being answered.

---

Built for the **In the Clouds** hackathon.
