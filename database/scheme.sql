-- =====================================================================
-- CloudCare database schema (PostgreSQL 15+ with pgvector)
-- Matching SQLAlchemy models: backend/app/models/
--
-- Run:  psql "$DATABASE_URL" -f database/scheme.sql
-- WARNING: drops and recreates all tables. Dev/hackathon use only.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector: embeddings for Foggy (RAG)
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

DROP TABLE IF EXISTS escalations, risk_scores, chat_messages, symptom_logs,
    medication_logs, medications, appointments, care_plan_chunks, care_plans,
    patients, users CASCADE;

-- ---------------------------------------------------------------------
-- Accounts
-- ---------------------------------------------------------------------

CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('patient', 'clinician')),
    full_name      TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Patient profile (1:1 with a patient user). Some fields double as ML features.
CREATE TABLE patients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    clinician_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    date_of_birth       DATE,
    procedure_name      TEXT NOT NULL,            -- 'Total knee replacement'
    procedure_type      TEXT NOT NULL,            -- ML category: 'orthopedic', 'abdominal', ...
    surgery_date        DATE NOT NULL,
    discharge_date      DATE,
    comorbidities       JSONB NOT NULL DEFAULT '[]',   -- ["diabetes", "smoker"]
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_patients_clinician ON patients(clinician_id);

-- ---------------------------------------------------------------------
-- Care plans (what the clinician uploads) + chunks for RAG
-- ---------------------------------------------------------------------

CREATE TABLE care_plans (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    created_by    UUID NOT NULL REFERENCES users(id),
    title         TEXT NOT NULL,
    raw_text      TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_care_plans_patient ON care_plans(patient_id);

-- vector(1024) must match the embedding model's output size
-- (voyage-3 = 1024, OpenAI text-embedding-3-small = 1536). Change in both places.
CREATE TABLE care_plan_chunks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_plan_id   UUID NOT NULL REFERENCES care_plans(id) ON DELETE CASCADE,
    patient_id     UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    chunk_index    INT  NOT NULL,
    section        TEXT,                          -- 'Wound care', 'When to call', ...
    content        TEXT NOT NULL,
    embedding      vector(1024),                  -- nullable: fill in once embeddings are added
    UNIQUE (care_plan_id, chunk_index)
);
CREATE INDEX idx_chunks_patient ON care_plan_chunks(patient_id);

-- ---------------------------------------------------------------------
-- Reminders
-- ---------------------------------------------------------------------

CREATE TABLE medications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    dosage          TEXT NOT NULL,
    instructions    TEXT,
    times_of_day    JSONB NOT NULL DEFAULT '[]',  -- ["08:00", "20:00"]
    start_date      DATE NOT NULL,
    end_date        DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_meds_patient ON medications(patient_id);

CREATE TABLE medication_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id   UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    scheduled_for   TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'taken', 'skipped', 'missed')),
    responded_at    TIMESTAMPTZ,
    UNIQUE (medication_id, scheduled_for)
);

CREATE TABLE appointments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    provider_name   TEXT,
    location        TEXT,
    scheduled_at    TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled', 'completed', 'missed', 'cancelled')),
    notes           TEXT
);
CREATE INDEX idx_appts_patient ON appointments(patient_id, scheduled_at);

-- ---------------------------------------------------------------------
-- Symptoms, chat, risk scores, escalations (human in the loop)
-- ---------------------------------------------------------------------

CREATE TABLE symptom_logs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id           UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    logged_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    source               TEXT NOT NULL DEFAULT 'checkin'
                         CHECK (source IN ('checkin', 'chat', 'voice')),
    pain_level           SMALLINT CHECK (pain_level BETWEEN 0 AND 10),
    temperature_f        NUMERIC(4,1),
    wound_redness        BOOLEAN NOT NULL DEFAULT FALSE,
    wound_drainage       BOOLEAN NOT NULL DEFAULT FALSE,
    swelling             BOOLEAN NOT NULL DEFAULT FALSE,
    nausea               BOOLEAN NOT NULL DEFAULT FALSE,
    shortness_of_breath  BOOLEAN NOT NULL DEFAULT FALSE,
    mobility_level       SMALLINT CHECK (mobility_level BETWEEN 0 AND 4),  -- 0 bedbound .. 4 normal
    free_text            TEXT
);
CREATE INDEX idx_symptoms_patient ON symptom_logs(patient_id, logged_at);

CREATE TABLE chat_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    role                TEXT NOT NULL CHECK (role IN ('patient', 'assistant', 'clinician')),
    content             TEXT NOT NULL,
    citations           JSONB NOT NULL DEFAULT '[]',   -- [{"chunk_id": "...", "section": "Wound care"}]
    answered_from_plan  BOOLEAN,                       -- FALSE = not covered by care plan
    red_flag            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_patient ON chat_messages(patient_id, created_at);

CREATE TABLE risk_scores (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    symptom_log_id   UUID REFERENCES symptom_logs(id) ON DELETE SET NULL,
    score            NUMERIC(4,3) NOT NULL CHECK (score BETWEEN 0 AND 1),
    risk_level       TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    model_version    TEXT NOT NULL,
    top_factors      JSONB NOT NULL DEFAULT '[]',     -- [{"feature": "temperature_f", "impact": 0.31}]
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_risk_patient ON risk_scores(patient_id, created_at);

CREATE TABLE escalations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    trigger_type     TEXT NOT NULL
                     CHECK (trigger_type IN ('red_flag', 'high_risk', 'unanswered_question', 'patient_request')),
    severity         TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'emergency')),
    summary          TEXT NOT NULL,
    chat_message_id  UUID REFERENCES chat_messages(id) ON DELETE SET NULL,
    risk_score_id    UUID REFERENCES risk_scores(id) ON DELETE SET NULL,
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'acknowledged', 'resolved')),
    reviewed_by      UUID REFERENCES users(id),
    clinician_notes  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at      TIMESTAMPTZ
);
CREATE INDEX idx_escalations_status ON escalations(status, created_at);
