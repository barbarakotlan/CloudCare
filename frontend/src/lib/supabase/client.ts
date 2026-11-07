import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
// Publishable key (sb_publishable_...) preferred; the legacy anon JWT still works.
const publicKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

/**
 * True when the configured key is a server-only key (sb_secret_... or a
 * service_role JWT). Those bypass every database protection and must never
 * ship to the browser, so the client refuses to use them.
 */
function isSecretKey(key: string): boolean {
  if (key.startsWith("sb_secret_")) return true;
  const payload = key.split(".")[1];
  if (!payload) return false;
  try {
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as { role?: unknown };
    return json.role === "service_role";
  } catch {
    return false;
  }
}

const keyIsSecret = Boolean(publicKey) && isSecretKey(publicKey);

export const isSupabaseConfigured = Boolean(url && publicKey) && !keyIsSecret;

export const SUPABASE_NOT_CONFIGURED = keyIsSecret
  ? "The Supabase key in the frontend env is a secret (service role) key. Remove it now and use the publishable key instead."
  : "Supabase sign-in isn't set up yet. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY to frontend/.env.local, or set NEXT_PUBLIC_AUTH_PROVIDER=backend.";

let client: SupabaseClient | null = null;

/** Browser Supabase client, or null when the env vars are missing (or unsafe). */
export function getSupabaseClient(): SupabaseClient | null {
  if (!isSupabaseConfigured) {
    if (keyIsSecret) console.error(SUPABASE_NOT_CONFIGURED);
    return null;
  }
  if (!client) {
    client = createClient(url, publicKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, storageKey: "cloudcare.supabase" },
    });
  }
  return client;
}
