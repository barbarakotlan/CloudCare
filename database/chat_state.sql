-- =====================================================================
-- CloudCare: Foggy conversation state (behavior policy v2).
--
-- Run once after database/scheme.sql (and supabase_rls.sql on Supabase):
--   psql "$DATABASE_URL" -f database/chat_state.sql
-- or paste into the Supabase SQL editor. Safe to re-run.
--
-- Apply BEFORE deploying the backend that includes app/models/chat_state.py:
-- the API reads chat_messages.route on every chat request.
-- Models: backend/app/models/chat_state.py, backend/app/models/triage.py.
-- =====================================================================

begin;

-- One row per patient, shared by text and voice: the contact offer waiting for a
-- yes/no answer and the check-in in progress. No message text is stored here
-- beyond the patient's words for a pending offer.
create table if not exists chat_sessions (
    patient_id      uuid primary key references patients(id) on delete cascade,
    pending_action  jsonb,       -- {"kind": "message_care_team", "recipient": "care_team", "reason", ...} or null
    checkin_state   jsonb,       -- {"awaiting", "answers", "clarifying", "first", "started_at"} or null
    updated_at      timestamptz not null default now()
);

-- Foggy's route per assistant message (EMERGENCY_911, CALL_SURGEON, REFUSE_DOSE_CHANGE,
-- START_CHECKIN, NOT_IN_PLAN, ANSWER_FROM_PLAN, OPERATIONAL). Null for older rows and
-- patient messages.
alter table chat_messages add column if not exists route text;

-- Same lockdown as supabase_rls.sql: only the API (postgres role) touches this table.
alter table public.chat_sessions enable row level security;
revoke all on table public.chat_sessions from anon, authenticated;

commit;

-- Check: rls_enabled = true, both *_select = false, and route_column = 1.
select c.relname                                          as table_name,
       c.relrowsecurity                                   as rls_enabled,
       has_table_privilege('anon', c.oid, 'select')          as anon_select,
       has_table_privilege('authenticated', c.oid, 'select') as authenticated_select,
       (select count(*) from information_schema.columns
         where table_schema = 'public' and table_name = 'chat_messages' and column_name = 'route') as route_column
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'chat_sessions';
