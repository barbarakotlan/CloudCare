import { getToken, handleUnauthorized } from "@/lib/auth/session";
import { ApiError, apiFetch } from "./client";

/** Mirrors backend/app/epic/schemas.py. */
export type EpicStatus = {
  connected: boolean;
  patient_fhir_id: string | null;
  issuer: string | null;
  connected_at: string | null;
  scopes: string[];
  last_sync_at: string | null;
  revoked: boolean;
  sandbox: boolean;
};

export type EpicMedication = {
  name: string;
  dose_text: string | null;
  frequency_text: string | null;
  status: string | null;
  authored_on: string | null;
  prescriber: string | null;
};

export type EpicLab = {
  name: string;
  value: string | null;
  unit: string | null;
  reference_range: string | null;
  status: string | null;
  effective_at: string | null;
  interpretation: string | null;
};

export type EpicEncounter = {
  type: string | null;
  class: string | null;
  start: string | null;
  end: string | null;
  location: string | null;
  reason: string | null;
};

export type EpicNote = {
  title: string;
  type: string | null;
  date: string | null;
  author: string | null;
  status: string | null;
  /** Plain text, at most 600 characters. Never HTML. */
  content_preview: string | null;
  /** True when content_preview is the whole note. */
  has_full_text: boolean;
};

export type EpicResourceKey = "medications" | "labs" | "encounters" | "notes";

export type EpicRecords = {
  medications: EpicMedication[];
  labs: EpicLab[];
  encounters: EpicEncounter[];
  notes: EpicNote[];
  missing: EpicResourceKey[];
  missing_reasons: Partial<Record<EpicResourceKey, string>>;
  fetched_at: string;
};

export const getEpicStatus = (signal?: AbortSignal) => apiFetch<EpicStatus>("/epic/status", { signal });

export const getEpicRecords = (signal?: AbortSignal) => apiFetch<EpicRecords>("/epic/records", { signal });

export const disconnectEpic = () => apiFetch<void>("/epic/connection", { method: "DELETE" });

/**
 * Asks the API (through our own /api/auth/epic route) for Epic's authorize URL.
 * The caller navigates there; Epic redirects back to /api/auth/callback/epic.
 */
export async function startEpicConnect(): Promise<string> {
  const token = getToken();
  if (!token) throw new ApiError(401, "Not logged in");

  let res: Response;
  try {
    res = await fetch("/api/auth/epic", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Couldn't reach CloudCare. Check your connection and try again.");
  }

  const data = (await res.json().catch(() => null)) as { authorize_url?: unknown; detail?: unknown } | null;
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const detail = typeof data?.detail === "string" ? data.detail : "Couldn't start MyChart sign-in.";
    throw new ApiError(res.status, detail);
  }
  if (typeof data?.authorize_url !== "string" || !data.authorize_url.startsWith("https://")) {
    throw new ApiError(502, "MyChart sign-in link was not valid.");
  }
  return data.authorize_url;
}

/** Human text for the ?reason= our callback route puts on the dashboard URL. */
export function epicErrorText(reason: string | null): string {
  switch (reason) {
    case "access_denied":
      return "You chose not to share your records. You can connect any time.";
    case "expired_state":
      return "The sign-in took longer than 10 minutes. Please try again.";
    case "invalid_state":
      return "That sign-in link was already used or isn't valid. Please try again.";
    case "state_mismatch":
      return "That MyChart sign-in wasn't started in this browser. Start it again from your CloudCare dashboard.";
    case "iss_mismatch":
    case "redirect_uri_mismatch":
      return "MyChart sent you back to an unexpected place, so we stopped. Please try again.";
    case "no_patient":
    case "invalid_patient":
      return "Epic didn't say which patient record to use. Sign in with a patient MyChart account.";
    case "unexpected_scope":
      return "Epic offered more access than CloudCare asks for, so we didn't connect.";
    case "token_exchange_failed":
      return "Epic didn't accept the sign-in. Please try again.";
    case "epic_unreachable":
      return "Couldn't reach Epic. Try again in a minute.";
    case "not_configured":
      return "MyChart connection isn't configured yet.";
    case "server_unreachable":
      return "Couldn't reach the CloudCare server. Try again in a minute.";
    default:
      return "Something went wrong connecting MyChart. Please try again.";
  }
}
