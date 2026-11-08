-- =====================================================================
-- CloudCare: patient mobile number.
--
-- Run once on Supabase BEFORE deploying the API version that has
-- `Patient.phone` (backend/app/models/user.py): every query that loads a
-- patient selects these columns, so the API fails until they exist.
--   psql "$DATABASE_URL" -f database/patient_phone.sql
-- or paste into the Supabase SQL editor. Safe to re-run. Additive only.
-- SQLite (local fallback) picks the columns up from the model automatically.
-- =====================================================================

begin;

-- E.164, e.g. +15551234567. Copied from the sign-up form (user_metadata.phone)
-- on first login, or set by the patient with PATCH /patients/me.
alter table public.patients add column if not exists phone text;
-- Set only once the number has been confirmed. No confirmation flow yet.
alter table public.patients add column if not exists phone_verified_at timestamptz;

-- Light sanity check; the API does the real validation (and refuses 911/N11/short codes).
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'patients_phone_e164_check'
    ) then
        alter table public.patients
            add constraint patients_phone_e164_check
            check (phone is null or phone ~ '^\+[1-9][0-9]{7,14}$');
    end if;
end $$;

commit;

-- Check: two rows, phone (text) and phone_verified_at (timestamp with time zone).
select column_name, data_type
from information_schema.columns
where table_schema = 'public' and table_name = 'patients'
  and column_name in ('phone', 'phone_verified_at')
order by column_name;
