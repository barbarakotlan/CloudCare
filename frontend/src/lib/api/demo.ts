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

export const resetDemoPatient = () => apiFetch<DemoResetOut>("/demo/reset", { method: "POST" });

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
