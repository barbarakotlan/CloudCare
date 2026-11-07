import "server-only";

/**
 * Base URL for server-to-server calls from route handlers to the FastAPI backend.
 * CLOUDCARE_API_URL is server-only (never shipped to the browser); it falls back
 * to the public API URL so local dev works with a single setting.
 */
export function cloudcareApiUrl(path: string): string {
  const base = (process.env.CLOUDCARE_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /\/$/,
    "",
  );
  return `${base}${path}`;
}

/** Render's free tier can take ~50 s to wake up, so allow a generous wait. */
export const BACKEND_TIMEOUT_MS = 60_000;
