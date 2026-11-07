import type { Role } from "@/lib/api/types";
import type { Session } from "./session";

export type AuthProviderName = "backend" | "supabase";

/** The one auth interface the UI talks to. */
export interface AuthProvider {
  readonly name: AuthProviderName;
  /** Signs in and stores the session. `role` is the role the user picked on the login screen. */
  login(email: string, password: string, role: Role): Promise<Session>;
  logout(): Promise<void>;
  getSession(): Session | null;
  getToken(): string | null;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export const ROLE_LABEL: Record<Role, string> = { patient: "Patient", clinician: "Doctor" };

export function roleMismatchMessage(actual: Role): string {
  return actual === "clinician"
    ? "That's a care-team account. Switch to Doctor above to sign in."
    : "That's a patient account. Switch to Patient above to sign in.";
}
