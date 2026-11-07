import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const isSupabaseConfigured = Boolean(url && anonKey);

export const SUPABASE_NOT_CONFIGURED =
  "Supabase sign-in isn't set up yet. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to frontend/.env.local, or set NEXT_PUBLIC_AUTH_PROVIDER=backend.";

let client: SupabaseClient | null = null;

/** Browser Supabase client, or null when the env vars are missing. */
export function getSupabaseClient(): SupabaseClient | null {
  if (!isSupabaseConfigured) return null;
  if (!client) {
    client = createClient(url, anonKey, {
      auth: { persistSession: true, autoRefreshToken: true, storageKey: "cloudcare.supabase" },
    });
  }
  return client;
}
