import { ApiError, apiFetch } from "./client";

/**
 * Shared demo patient reset.
 *
 *   POST /demo/reset -> { reset: true, counts: { table: rows_deleted }, restored?: {...} }
 *
 * Clears Jordan Lee's chats, alerts, check-ins and dose answers for everyone using the
 * demo. The server decides who may call it (clinicians and demo accounts).
 */
export type DemoResetOut = {
  reset: boolean;
  counts: Record<string, number>;
  restored?: Record<string, number>;
};

export const DEMO_RESET_LABEL = "Resets Jordan Lee's chats, alerts and check-ins for everyone using the demo";

export const resetDemoPatient = (signal?: AbortSignal) =>
  apiFetch<DemoResetOut>("/demo/reset", { method: "POST", signal });

/** Longest a sign-in waits for the fresh-demo reset before going on to the dashboard. */
export const SIGN_IN_RESET_TIMEOUT_MS = 8000;

/**
 * Whether signing in as this user starts a fresh demo: the shared demo patient only.
 * The demo clinician keeps the queue as it is.
 */
export function startsFreshDemo(user: { role: string; email?: string | null }): boolean {
  return user.role === "patient" && isDemoEmail(user.email);
}

/**
 * Resets the demo patient right after sign-in, giving up after `timeoutMs`.
 * Never throws: an older server without the route (404), the rate limit (429) or a
 * network problem just means the visitor sees the demo as it was. Returns whether it reset.
 */
export async function resetDemoOnSignIn(timeoutMs = SIGN_IN_RESET_TIMEOUT_MS): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    await resetDemoPatient(controller.signal);
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Whether this server has the reset route, without calling it: a GET on a POST-only
 * route answers 405, a missing route 404. Nothing is changed.
 */
export async function demoResetAvailable(signal?: AbortSignal): Promise<boolean> {
  try {
    await apiFetch<unknown>("/demo/reset", { auth: false, signal });
    return true;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    if (err instanceof ApiError) return err.status !== 404 && err.status !== 0;
    return false;
  }
}

export function isDemoEmail(email: string | undefined | null): boolean {
  return Boolean(email && email.trim().toLowerCase().endsWith("@demo.com"));
}
