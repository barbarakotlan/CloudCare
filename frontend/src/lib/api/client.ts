import { getToken, handleUnauthorized } from "@/lib/auth/session";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ValidationIssue = { msg?: string; loc?: Array<string | number> };

function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const issues = detail as ValidationIssue[];
    const parts = issues
      .map((d) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        return d.msg ? (field ? `${field}: ${d.msg}` : d.msg) : null;
      })
      .filter((m): m is string => Boolean(m));
    if (parts.length) return parts.join("; ");
  }
  return fallback;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Attach the bearer token (default true). */
  auth?: boolean;
  /**
   * Send this bearer token instead of the stored one (e.g. to check a token
   * before saving it). A 401 then leaves the stored session alone.
   */
  token?: string;
  signal?: AbortSignal;
};

/** fetch wrapper: JSON in/out, bearer token, readable errors. */
export async function apiFetch<T>(
  path: string,
  { method = "GET", body, auth = true, token: explicitToken, signal }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = explicitToken ?? (auth ? getToken() : null);
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, `Can't reach the CloudCare server at ${API_URL}. Is the backend running?`);
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = ((await res.json()) as { detail?: unknown }).detail;
    } catch {
      // Non-JSON error body.
    }
    const message = messageFromDetail(detail, res.statusText || `Request failed (${res.status})`);
    if (res.status === 401 && auth && explicitToken === undefined) handleUnauthorized();
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
