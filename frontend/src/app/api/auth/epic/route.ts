import { NextResponse, type NextRequest } from "next/server";
import { EPIC_STATE_COOKIE, EPIC_STATE_COOKIE_PATH, EPIC_STATE_MAX_AGE } from "@/lib/server/epicState";
import { BACKEND_TIMEOUT_MS, cloudcareApiUrl } from "@/lib/server/cloudcareApi";

// Start of the MyChart connect flow.
//
// The dashboard calls this with fetch() and the patient's bearer token. We pass the
// token through to FastAPI, which records a single-use state + PKCE verifier and
// returns Epic's authorize URL. The browser then navigates there itself.
//
// The state is also put in a short-lived HttpOnly cookie scoped to the callback path.
// The callback only completes when the browser coming back from Epic carries that
// cookie, so an authorize link started on someone else's account and sent to a victim
// can't attach the victim's MyChart records to the sender's CloudCare account.
//
// No `runtime`/`dynamic` exports: this app has cacheComponents on, which rejects
// both. POST handlers are never cached, and the default runtime is Node.

const NO_STORE = { "Cache-Control": "no-store" };

export async function POST(request: NextRequest) {
  // Defense in depth: the bearer token already rules out cross-site requests.
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Cross-site request refused" }, { status: 403, headers: NO_STORE });
  }

  const authorization = request.headers.get("authorization");
  if (!authorization || !/^Bearer\s+\S+$/.test(authorization)) {
    return NextResponse.json({ detail: "Not logged in" }, { status: 401, headers: NO_STORE });
  }

  let res: Response;
  try {
    res = await fetch(cloudcareApiUrl("/epic/connect/start"), {
      method: "POST",
      headers: { Authorization: authorization, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });
  } catch {
    return NextResponse.json(
      { detail: "Can't reach the CloudCare server right now. Try again in a minute." },
      { status: 502, headers: NO_STORE },
    );
  }

  const data = (await res.json().catch(() => null)) as { authorize_url?: unknown; detail?: unknown } | null;
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "Couldn't start MyChart sign-in.";
    return NextResponse.json({ detail }, { status: res.status, headers: NO_STORE });
  }

  const authorizeUrl = data?.authorize_url;
  let state: string | null = null;
  if (typeof authorizeUrl === "string" && authorizeUrl.startsWith("https://")) {
    try {
      state = new URL(authorizeUrl).searchParams.get("state");
    } catch {
      state = null;
    }
  }
  if (typeof authorizeUrl !== "string" || !state) {
    return NextResponse.json({ detail: "MyChart sign-in link was not valid." }, { status: 502, headers: NO_STORE });
  }

  const response = NextResponse.json({ authorize_url: authorizeUrl }, { headers: NO_STORE });
  response.cookies.set(EPIC_STATE_COOKIE, state, {
    httpOnly: true,
    // Lax: sent on the top-level GET redirect back from Epic, never on cross-site subrequests.
    sameSite: "lax",
    secure: request.nextUrl.protocol === "https:",
    path: EPIC_STATE_COOKIE_PATH,
    maxAge: EPIC_STATE_MAX_AGE,
  });
  return response;
}
