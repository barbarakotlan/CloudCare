import { NextResponse, type NextRequest } from "next/server";
import { BACKEND_TIMEOUT_MS, cloudcareApiUrl } from "@/lib/server/cloudcareApi";
import { EPIC_STATE_COOKIE, EPIC_STATE_COOKIE_PATH, stateMatches } from "@/lib/server/epicState";

// Epic redirects the browser here after MyChart sign-in (this is the redirect URI
// registered on the Epic app). We hand `code` + `state` to FastAPI server to
// server; it checks the state, exchanges the code and stores the tokens encrypted.
// Tokens never reach the browser: the patient just lands back on the dashboard.
//
// No `runtime`/`dynamic` exports: cacheComponents rejects both, and reading the
// request's search params already makes this handler run per request.

const DASHBOARD = "/patient/dashboard";

// Reasons we are willing to echo into the dashboard URL. Anything else from the
// backend or Epic is collapsed to a generic code so nothing arbitrary is reflected.
const KNOWN_REASONS = new Set([
  "access_denied",
  "epic_error",
  "missing_code",
  "invalid_state",
  "expired_state",
  "state_mismatch",
  "iss_mismatch",
  "redirect_uri_mismatch",
  "no_patient",
  "invalid_patient",
  "unexpected_scope",
  "token_exchange_failed",
  "epic_unreachable",
  "not_configured",
  "server_unreachable",
  "connect_failed",
]);

function finish(request: NextRequest, outcome: { ok: true } | { ok: false; reason: string }) {
  const params = new URLSearchParams();
  if (outcome.ok) {
    params.set("epic", "connected");
  } else {
    params.set("epic", "error");
    params.set("reason", KNOWN_REASONS.has(outcome.reason) ? outcome.reason : "connect_failed");
  }
  // Sign-in usually runs in a popup. The dashboard checks for an opener and,
  // if there is one, hands it the result and closes; otherwise it loads normally.
  params.set("popup", "1");

  // A fixed, relative Location: the destination never depends on the request's Host
  // header or on anything Epic or the backend sent, so this can't become an open redirect.
  const response = new NextResponse(null, {
    status: 303,
    headers: {
      Location: `${DASHBOARD}?${params.toString()}`,
      "Cache-Control": "no-store",
      // The URL we were called with carries the authorization code; don't leak it.
      "Referrer-Policy": "no-referrer",
    },
  });
  // The binding cookie is single use, whatever the outcome.
  response.cookies.set(EPIC_STATE_COOKIE, "", { path: EPIC_STATE_COOKIE_PATH, maxAge: 0 });
  if (outcome.ok) {
    // UX hint only ("just connected"); holds nothing sensitive.
    response.cookies.set("cloudcare_epic", "connected", {
      httpOnly: true,
      sameSite: "lax",
      secure: request.nextUrl.protocol === "https:",
      path: "/",
      maxAge: 600,
    });
  }
  return response;
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  const epicError = params.get("error");
  if (epicError) {
    return finish(request, { ok: false, reason: epicError === "access_denied" ? "access_denied" : "epic_error" });
  }

  const code = params.get("code");
  const state = params.get("state");
  if (!code || !state) return finish(request, { ok: false, reason: "missing_code" });

  // Only the browser that started this sign-in may finish it (see lib/server/epicState.ts).
  if (!stateMatches(request.cookies.get(EPIC_STATE_COOKIE)?.value, state)) {
    return finish(request, { ok: false, reason: "state_mismatch" });
  }

  const body: { code: string; state: string; iss?: string } = { code, state };
  const iss = params.get("iss");
  if (iss) body.iss = iss;

  let res: Response;
  try {
    res = await fetch(cloudcareApiUrl("/epic/connect/callback"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });
  } catch {
    return finish(request, { ok: false, reason: "server_unreachable" });
  }

  if (res.ok) return finish(request, { ok: true });

  if (res.status === 503) return finish(request, { ok: false, reason: "not_configured" });
  const data = (await res.json().catch(() => null)) as { detail?: unknown } | null;
  const reason = typeof data?.detail === "string" ? data.detail : "connect_failed";
  return finish(request, { ok: false, reason });
}
