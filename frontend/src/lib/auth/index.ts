import { backendAuth } from "./backend";
import { supabaseAuth } from "./supabase";
import type { AuthProvider, AuthProviderName } from "./types";

export { AuthError, ROLE_LABEL, type AuthProvider, type AuthProviderName } from "./types";
export { getToken, type Session, type SessionUser } from "./session";

const configured = (process.env.NEXT_PUBLIC_AUTH_PROVIDER ?? "backend").toLowerCase();

export const AUTH_PROVIDER_NAME: AuthProviderName = configured === "supabase" ? "supabase" : "backend";

/** The active provider, chosen by NEXT_PUBLIC_AUTH_PROVIDER (default `backend`). */
export const auth: AuthProvider = AUTH_PROVIDER_NAME === "supabase" ? supabaseAuth : backendAuth;

export const login: AuthProvider["login"] = (email, password, role) => auth.login(email, password, role);
export const getSession: AuthProvider["getSession"] = () => auth.getSession();

/** Clears the session and hard-navigates so no state from the previous user survives. */
export async function logout(redirectTo = "/") {
  await auth.logout();
  window.location.href = redirectTo;
}

export function dashboardPathFor(role: "patient" | "clinician"): "/patient/dashboard" | "/clinician/dashboard" {
  return role === "clinician" ? "/clinician/dashboard" : "/patient/dashboard";
}
