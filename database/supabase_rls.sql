-- =====================================================================
-- CloudCare on Supabase: keep every table out of the Data API.
--
-- The FastAPI backend is the only thing that reads or writes these tables.
-- It connects as the `postgres` role, which owns the tables and bypasses
-- row level security, so nothing here changes how the backend behaves.
--
-- What this does for the browser-facing roles (`anon`, `authenticated`):
--   1. RLS on, with no policies  -> zero rows visible even if a grant slips in.
--   2. Table and sequence grants revoked -> /rest/v1 and /graphql/v1 return
--      permission denied instead of data.
--   3. Default privileges revoked -> tables created later by `postgres`
--      start locked down too.
--
-- Run after database/scheme.sql, and again every time scheme.sql is re-run
-- (it drops and recreates the tables, which resets RLS and grants):
--   psql "$DATABASE_URL" -f database/scheme.sql
--   psql "$DATABASE_URL" -f database/supabase_rls.sql
-- or paste both into the Supabase SQL editor.
--
-- The Security Advisor will list these tables as "RLS enabled, no policy".
-- That is expected: no policy is the policy.
-- =====================================================================

begin;

alter table public.users             enable row level security;
alter table public.patients          enable row level security;
alter table public.care_plans        enable row level security;
alter table public.care_plan_chunks  enable row level security;
alter table public.medications       enable row level security;
alter table public.medication_logs   enable row level security;
alter table public.appointments      enable row level security;
alter table public.symptom_logs      enable row level security;
alter table public.chat_messages     enable row level security;
alter table public.risk_scores       enable row level security;
alter table public.escalations       enable row level security;

revoke all on table
    public.users, public.patients, public.care_plans, public.care_plan_chunks,
    public.medications, public.medication_logs, public.appointments,
    public.symptom_logs, public.chat_messages, public.risk_scores, public.escalations
from anon, authenticated;

alter default privileges for role postgres in schema public
    revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
    revoke all on sequences from anon, authenticated;

commit;

-- Check: every row should show rls_enabled = true and both *_select = false.
select c.relname                                          as table_name,
       c.relrowsecurity                                   as rls_enabled,
       has_table_privilege('anon', c.oid, 'select')          as anon_select,
       has_table_privilege('authenticated', c.oid, 'select') as authenticated_select
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
order by c.relname;
