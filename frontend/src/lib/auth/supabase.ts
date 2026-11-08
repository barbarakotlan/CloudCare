import type { Session as SupabaseSession, User as SupabaseUser } from "@supabase/supabase-js";
import { ApiError, apiFetch, errorMessage } from "@/lib/api/client";
import type { Role, UserOut } from "@/lib/api/types";
import { getSupabaseClient, SUPABASE_NOT_CONFIGURED } from "@/lib/supabase/client";
import { clearSession, getToken, readSession, writeSession, type Session, type SessionUser } from "./session";
import { AuthError, roleMismatchMessage, type AuthProvider } from "./types";

/**
 * Supabase email + password sign-in.
 *
 * Supabase issues the access token; the FastAPI backend verifies it and owns
 * the user record. The role comes from `app_metadata.role` (only the service
 * role can set it); `user_metadata` is user-editable and is only used for the
 * display name. The token is mirrored into the shared `cloudcare.token` /
 * `cloudcare.user` storage so the API client and useSession() work unchanged,
 * and SupabaseSessionSync keeps it fresh as Supabase refreshes the token.
 */

function roleFromUser(user: SupabaseUser): Role {
  return user.app_metadata?.role === "clinician" ? "clinician" : "patient";
}

function sessionUserFromSupabase(user: SupabaseUser): SessionUser {
  const meta = user.user_metadata as { full_name?: unknown } | undefined;
  const fullName = typeof meta?.full_name === "string" && meta.full_name.trim() ? meta.full_name.trim() : user.email ?? "";
  return { id: user.id, full_name: fullName, role: roleFromUser(user), email: user.email ?? undefined };
}

/** Asks the backend who this token belongs to (creates the user row on first sign-in). */
async function fetchBackendUser(token: string): Promise<UserOut> {
  return apiFetch<UserOut>("/auth/me", { token });
}

function backendRejectionMessage(err: unknown): string {
  if (err instanceof ApiError && (err.status === 401 || err.status === 503)) {
    return `The CloudCare server didn't accept the Supabase sign-in (${err.message}). Check SUPABASE_URL on the backend.`;
  }
  return errorMessage(err);
}

function sameAccount(a: SessionUser, email: string | undefined): boolean {
  if (!email || !a.email) return false;
  return a.email.toLowerCase() === email.toLowerCase();
}

/**
 * Mirrors a Supabase session into the shared storage. Called on page load and
 * on every Supabase auth event (see SupabaseSessionSync).
 */
export function syncFromSupabase(session: SupabaseSession | null): void {
  if (!session) {
    if (readSession()) clearSession();
    return;
  }
  const token = session.access_token;
  const stored = readSession();
  if (stored && sameAccount(stored.user, session.user.email)) {
    // Same person, refreshed token: keep the backend's view of the user.
    if (stored.token !== token) writeSession({ token, user: stored.user });
    return;
  }

  // New sign-in we didn't initiate here (e.g. the email confirmation link):
  // store what the token says, then let the backend fill in its view.
  writeSession({ token, user: sessionUserFromSupabase(session.user) });
  void fetchBackendUser(token)
    .then((me) => {
      if (getToken() !== token) return; // signed out or switched meanwhile
      writeSession({ token, user: { ...me, email: session.user.email ?? undefined } });
    })
    .catch(() => {
      // Dashboards surface API errors themselves.
    });
}

export type SignUpResult = { session: Session | null; needsEmailConfirmation: boolean };

/** Creates a patient account. Clinician accounts are only created by the backend seed. */
export async function signUpPatient(
  fullName: string,
  email: string,
  password: string,
  /** Mobile number in E.164, or null. Copied onto the patient profile on first sign-in. */
  phone: string | null = null,
): Promise<SignUpResult> {
  const supabase = getSupabaseClient();
  if (!supabase) throw new AuthError(SUPABASE_NOT_CONFIGURED);

  const { data, error } = await supabase.auth.signUp({
    email: email.trim(),
    password,
    options: {
      // Display name and contact number only. The role is never taken from user_metadata.
      data: phone ? { full_name: fullName.trim(), phone } : { full_name: fullName.trim() },
      emailRedirectTo: `${window.location.origin}/login`,
    },
  });
  if (error) throw new AuthError(error.message);
  if (!data.session) return { session: null, needsEmailConfirmation: true };

  const token = data.session.access_token;
  let me: UserOut;
  try {
    me = await fetchBackendUser(token);
  } catch (err) {
    await supabase.auth.signOut().catch(() => undefined);
    clearSession();
    throw new AuthError(backendRejectionMessage(err));
  }
  const session: Session = { token, user: { ...me, email: data.session.user.email ?? email.trim() } };
  writeSession(session);
  return { session, needsEmailConfirmation: false };
}

/** Path Supabase sends people back to from a password reset email. */
export const RESET_PASSWORD_PATH = "/reset-password";

/**
 * Emails a password reset link. Supabase answers the same way whether or not the
 * address has an account, so the caller shows one neutral message.
 */
export async function requestPasswordReset(email: string): Promise<void> {
  const supabase = getSupabaseClient();
  if (!supabase) throw new AuthError(SUPABASE_NOT_CONFIGURED);
  const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
    redirectTo: `${window.location.origin}${RESET_PASSWORD_PATH}`,
  });
  if (error) throw new AuthError(error.message);
}

/**
 * Sets a new password on the recovery session from the reset link, then signs that
 * session into CloudCare the same way a normal sign-in does.
 */
export async function completePasswordReset(password: string): Promise<Session> {
  const supabase = getSupabaseClient();
  if (!supabase) throw new AuthError(SUPABASE_NOT_CONFIGURED);

  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw new AuthError(error.message);

  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new AuthError("Your reset link has expired. Ask for a new one from the sign-in page.");

  const token = data.session.access_token;
  let me: UserOut;
  try {
    me = await fetchBackendUser(token);
  } catch (err) {
    throw new AuthError(backendRejectionMessage(err));
  }
  const session: Session = { token, user: { ...me, email: data.session.user.email ?? undefined } };
  writeSession(session);
  return session;
}

export const supabaseAuth: AuthProvider = {
  name: "supabase",

  async login(email: string, password: string, role: Role): Promise<Session> {
    const supabase = getSupabaseClient();
    if (!supabase) throw new AuthError(SUPABASE_NOT_CONFIGURED);

    const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    if (error || !data.session || !data.user) {
      throw new AuthError(error?.message ?? "Supabase sign-in failed.");
    }

    const token = data.session.access_token;
    let me: UserOut;
    try {
      me = await fetchBackendUser(token);
    } catch (err) {
      await supabase.auth.signOut().catch(() => undefined);
      clearSession();
      throw new AuthError(backendRejectionMessage(err));
    }

    if (me.role !== role) {
      await supabase.auth.signOut().catch(() => undefined);
      clearSession();
      throw new AuthError(roleMismatchMessage(me.role));
    }

    const session: Session = { token, user: { ...me, email: data.user.email ?? email.trim() } };
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
