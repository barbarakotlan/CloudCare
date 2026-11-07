import type { Role } from "@/lib/api/types";
import { getSupabaseClient, SUPABASE_NOT_CONFIGURED } from "@/lib/supabase/client";
import { clearSession, getToken, readSession, writeSession, type Session } from "./session";
import { AuthError, roleMismatchMessage, type AuthProvider } from "./types";

/**
 * Optional provider: Supabase email + password.
 * The role comes from the Supabase user's `user_metadata.role`.
 *
 * NOTE: today the FastAPI backend only accepts its own JWTs, so API calls
 * made with a Supabase token will 401 until the backend verifies Supabase
 * JWTs (see "Auth decision" in CLAUDE.md). Only this file changes then.
 */
export const supabaseAuth: AuthProvider = {
  name: "supabase",

  async login(email: string, password: string, role: Role): Promise<Session> {
    const supabase = getSupabaseClient();
    if (!supabase) throw new AuthError(SUPABASE_NOT_CONFIGURED);

    const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    if (error || !data.session || !data.user) {
      throw new AuthError(error?.message ?? "Supabase sign-in failed.");
    }

    const metaRole = data.user.user_metadata?.role;
    const actualRole: Role = metaRole === "clinician" ? "clinician" : "patient";
    if (actualRole !== role) {
      await supabase.auth.signOut();
      throw new AuthError(roleMismatchMessage(actualRole));
    }

    const fullName =
      typeof data.user.user_metadata?.full_name === "string" ? data.user.user_metadata.full_name : email.trim();
    const session: Session = {
      token: data.session.access_token,
      user: { id: data.user.id, full_name: fullName, role: actualRole, email: data.user.email ?? email.trim() },
    };
    writeSession(session);
    return session;
  },

  async logout() {
    const supabase = getSupabaseClient();
    if (supabase) await supabase.auth.signOut().catch(() => undefined);
    clearSession();
  },

  getSession: readSession,
  getToken,
};
