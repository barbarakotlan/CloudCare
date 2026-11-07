import type { NextRequest } from "next/server";
import { BACKEND_TIMEOUT_MS, cloudcareApiUrl } from "@/lib/server/cloudcareApi";

// Start of the MyChart connect flow.
//
// The dashboard calls this with fetch() and the patient's bearer token. We pass the
// token through to FastAPI, which records a single-use state + PKCE verifier and
// returns Epic's authorize URL. The browser then navigates there itself.
//
// No `runtime`/`dynamic` exports: this app has cacheComponents on, which rejects
// both. POST handlers are never cached, and the default runtime is Node.

const NO_STORE = { "Cache-Control": "no-store" };

export async function POST(request: NextRequest) {
  const authorization = request.headers.get("authorization");
  if (!authorization || !/^Bearer\s+\S+$/.test(authorization)) {
    return Response.json({ detail: "Not logged in" }, { status: 401, headers: NO_STORE });
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
    return Response.json(
      { detail: "Can't reach the CloudCare server right now. Try again in a minute." },
      { status: 502, headers: NO_STORE },
    );
  }

  const data = (await res.json().catch(() => null)) as { authorize_url?: unknown; detail?: unknown } | null;
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "Couldn't start MyChart sign-in.";
    return Response.json({ detail }, { status: res.status, headers: NO_STORE });
  }

  const authorizeUrl = data?.authorize_url;
  if (typeof authorizeUrl !== "string" || !authorizeUrl.startsWith("https://")) {
    return Response.json({ detail: "MyChart sign-in link was not valid." }, { status: 502, headers: NO_STORE });
  }
  return Response.json({ authorize_url: authorizeUrl }, { headers: NO_STORE });
}
