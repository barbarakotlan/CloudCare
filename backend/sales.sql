-- =====================================================================
-- CloudCare: onboarding requests from the public sales chat.
--
-- Run once (no dependency on the patient tables):
--   psql "$DATABASE_URL" -f backend/sales.sql
-- or paste into the Supabase SQL editor. Safe to re-run.
--
-- sales_leads holds the work contact details a hospital visitor typed into
-- the chat's onboarding form, plus the chat transcript (at most 40 turns).
-- sales_emails holds the email to the team inbox, rendered by the API and
-- stored with status 'stored'. When RESEND_API_KEY is set the API also sends
-- it and records 'sent' (provider_id) or 'failed' (error). No patient data here.
-- Models: backend/app/models/sales.py.
-- =====================================================================

begin;

create table if not exists sales_leads (
    id                    uuid primary key default gen_random_uuid(),
    created_at            timestamptz not null default now(),
    session_id            text,
    hospital              text not null,
    contact_name          text not null,
    role                  text not null,
    work_email            text not null,
    phone                 text,
    discharges_per_month  text,
    ehr                   text,
    service_lines         text,
    timeline              text,
    notes                 text,
    source_page           text,
    transcript            jsonb
);
create index if not exists ix_sales_leads_created_at on sales_leads(created_at);

create table if not exists sales_emails (
    id          uuid primary key default gen_random_uuid(),
    lead_id     uuid not null references sales_leads(id) on delete cascade,
    to_address  text not null,
    subject     text not null,
    body        text not null,
    status      varchar(16) not null default 'stored',
    created_at  timestamptz not null default now()
);
create index if not exists ix_sales_emails_created_at on sales_emails(created_at);
create index if not exists ix_sales_emails_lead_id on sales_emails(lead_id);
-- Delivery outcome (added after the first release; safe on an existing table).
alter table sales_emails add column if not exists provider_id text;
alter table sales_emails add column if not exists error text;

-- Same lockdown as database/supabase_rls.sql: only the API (postgres role) touches them.
alter table public.sales_leads enable row level security;
alter table public.sales_emails enable row level security;
revoke all on table public.sales_leads from anon, authenticated;
revoke all on table public.sales_emails from anon, authenticated;

commit;

-- Check: rls_enabled = true, both *_select = false.
select c.relname                                             as table_name,
       c.relrowsecurity                                      as rls_enabled,
       has_table_privilege('anon', c.oid, 'select')          as anon_select,
       has_table_privilege('authenticated', c.oid, 'select') as authenticated_select
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in ('sales_leads', 'sales_emails');
