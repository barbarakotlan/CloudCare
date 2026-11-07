-- =====================================================================
-- CloudCare: Epic MyChart (SMART on FHIR) connection tables.
--
-- Run once after database/scheme.sql (and supabase_rls.sql on Supabase):
--   psql "$DATABASE_URL" -f database/epic.sql
-- or paste into the Supabase SQL editor. Safe to re-run.
--
-- Tokens are stored Fernet-encrypted by the API (EPIC_TOKEN_ENCRYPTION_KEY);
-- the database never sees them in clear text. No clinical data is stored:
-- records are fetched live from Epic on request.
-- Models: backend/app/models/epic.py.
-- =====================================================================

begin;

-- One pending authorize request per row. Single use; expires after 10 minutes.
create table if not exists epic_oauth_states (
    state           varchar(128) primary key,
    user_id         uuid not null references users(id) on delete cascade,
    code_verifier   text not null,              -- PKCE verifier, encrypted
    iss             text not null,              -- FHIR base the request was made for
    redirect_uri    text not null,
    created_at      timestamptz not null default now(),
    expires_at      timestamptz not null
);
create index if not exists ix_epic_oauth_states_user_id on epic_oauth_states(user_id);
create index if not exists ix_epic_oauth_states_expires_at on epic_oauth_states(expires_at);

-- A patient's MyChart link. One per CloudCare user.
create table if not exists epic_connections (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null unique references users(id) on delete cascade,
    iss                 text not null,
    patient_fhir_id     varchar(64) not null,
    access_token_enc    text not null,
    refresh_token_enc   text,
    token_type          varchar(32) not null default 'Bearer',
    scope               text not null default '',
    expires_at          timestamptz,
    id_token_sub        varchar(255),
    status              varchar(16) not null default 'active',
    connected_at        timestamptz not null,
    last_sync_at        timestamptz,
    constraint epic_connections_status_check check (status in ('active', 'revoked'))
);

-- Same lockdown as supabase_rls.sql: only the API (postgres role) touches these.
alter table public.epic_oauth_states enable row level security;
alter table public.epic_connections  enable row level security;
revoke all on table public.epic_oauth_states, public.epic_connections from anon, authenticated;

commit;

-- Check: both rows should show rls_enabled = true and both *_select = false.
select c.relname                                          as table_name,
       c.relrowsecurity                                   as rls_enabled,
       has_table_privilege('anon', c.oid, 'select')          as anon_select,
       has_table_privilege('authenticated', c.oid, 'select') as authenticated_select
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in ('epic_oauth_states', 'epic_connections')
order by c.relname;
