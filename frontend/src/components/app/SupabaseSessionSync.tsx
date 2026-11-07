"use client";

import { useEffect } from "react";
import { syncFromSupabase } from "@/lib/auth/supabase";
import { getSupabaseClient } from "@/lib/supabase/client";

/**
 * Keeps the stored API token in step with Supabase: restores the session on
 * load and follows sign-in, token refresh and sign-out (including from other
 * tabs). Mounted once from the root layout when the Supabase provider is on.
 */
export function SupabaseSessionSync() {
  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) return;
    let active = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (active) syncFromSupabase(data.session);
    });

    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      // Keep this callback synchronous: awaiting Supabase calls in here can deadlock the client.
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED" || event === "USER_UPDATED" || event === "SIGNED_OUT") {
        syncFromSupabase(event === "SIGNED_OUT" ? null : session);
      }
    });

    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  return null;
}
