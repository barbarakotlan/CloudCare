-- =====================================================================
-- CloudCare: texts and calls placed to a patient's own phone.
--
-- Run once after database/patient_phone.sql:
--   psql "$DATABASE_URL" -f database/outreach.sql
-- or paste into the Supabase SQL editor. Safe to re-run.
--
-- Only the last four digits of the destination are stored. No message text,
-- call audio, or transcript is kept here. Model: backend/app/models/outreach.py.
-- Without this table the API still texts and calls (rate limits fall back to
-- memory) and logs "outreach.log.unavailable".
-- =====================================================================

begin;

create table if not exists outreach_log (
    id               uuid primary key default gen_random_uuid(),
    patient_id       uuid not null references patients(id) on delete cascade,
    kind             varchar(32) not null,          -- 'checkin' | 'plan_summary'
    channel          varchar(8)  not null,          -- 'sms' | 'call'
    to_number_last4  varchar(4)  not null,
    status           varchar(16) not null,          -- 'sent' | 'started' | 'failed'
    provider_id      varchar(64),                   -- Twilio SM... sid or ElevenLabs conversation id
    created_at       timestamptz not null default now(),
    constraint outreach_log_channel_check check (channel in ('sms', 'call')),
    constraint outreach_log_status_check check (status in ('sent', 'started', 'failed'))
);
create index if not exists ix_outreach_log_patient_channel_created
    on outreach_log(patient_id, channel, created_at);

-- Same lockdown as supabase_rls.sql: only the API (postgres role) touches it.
alter table public.outreach_log enable row level security;
revoke all on table public.outreach_log from anon, authenticated;

commit;

-- Check: rls_enabled = true, both *_select = false.
select c.relname                                             as table_name,
       c.relrowsecurity                                      as rls_enabled,
       has_table_privilege('anon', c.oid, 'select')          as anon_select,
       has_table_privilege('authenticated', c.oid, 'select') as authenticated_select
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'outreach_log';
