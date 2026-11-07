import type { AuthProviderName } from "./types";

const configured = (process.env.NEXT_PUBLIC_AUTH_PROVIDER ?? "backend").toLowerCase();

/** Which sign-in the app uses, from NEXT_PUBLIC_AUTH_PROVIDER (default `backend`). */
export const AUTH_PROVIDER_NAME: AuthProviderName = configured === "supabase" ? "supabase" : "backend";
