-- =====================================================================
-- CloudCare: when an escalation was acknowledged.
--
-- Run once after database/scheme.sql:
--   psql "$DATABASE_URL" -f database/escalations_ack.sql
-- or paste into the Supabase SQL editor. Safe to re-run.
--
-- Apply BEFORE deploying the backend that includes Escalation.acknowledged_at
-- (backend/app/models/triage.py): the API reads this column on every escalation query.
-- =====================================================================

begin;

-- Set by PATCH /escalations/{id} when status becomes 'acknowledged'; cleared on reopen;
-- kept when the escalation is later resolved. Null for rows acknowledged before this column.
alter table escalations add column if not exists acknowledged_at timestamptz;

commit;

-- Check: one row, data_type = 'timestamp with time zone'.
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public' and table_name = 'escalations' and column_name = 'acknowledged_at';
