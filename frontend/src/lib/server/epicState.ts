import "server-only";
import { timingSafeEqual } from "node:crypto";

/**
 * Binds a MyChart sign-in to the browser that started it.
 *
 * POST /api/auth/epic stores the OAuth `state` in this HttpOnly cookie (path limited to
 * the callback, 10 minutes, same as the server-side state). The callback refuses to
 * finish unless the `state` Epic sends back matches the cookie, so a sign-in link made
 * on one account can't be completed in another person's browser.
 */
export const EPIC_STATE_COOKIE = "cloudcare_epic_state";
export const EPIC_STATE_COOKIE_PATH = "/api/auth/callback/epic";
export const EPIC_STATE_MAX_AGE = 600;

export function stateMatches(cookieValue: string | undefined, state: string): boolean {
  if (!cookieValue || !state) return false;
  const a = Buffer.from(cookieValue);
  const b = Buffer.from(state);
  return a.length === b.length && timingSafeEqual(a, b);
}
