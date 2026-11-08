import { apiFetch } from "./client";

/** Mirrors backend/app/outreach/schemas.py. */
export type OutreachCapabilities = {
  sms: boolean;
  call: boolean;
  /** Plain-language reason per channel ("sms", "call") or for the number ("phone"). */
  reasons: Partial<Record<"sms" | "call" | "phone", string>>;
  phone_on_file: boolean;
  phone_last4: string | null;
  limits: { sms_seconds: number; call_seconds: number };
};

export type OutreachTextKind = "checkin" | "plan_summary";

/** `sent` means the texting service accepted it for delivery, not that it was read. */
export type OutreachTextResult = {
  status: "sent" | "failed";
  provider_id: string | null;
  to_last4: string;
  detail: string | null;
};

export type OutreachTextStatus = {
  provider_id: string;
  /** The texting service's own status: queued, sending, sent, delivered, undelivered, failed… */
  delivery: string;
  failed: boolean;
  detail: string | null;
};

/** `started` means the call is being dialed, not that anyone answered. */
export type OutreachCallResult = {
  status: "started" | "failed";
  conversation_id: string | null;
  to_last4: string;
  detail: string | null;
};

/** The part of PatientOut this feature reads (phone arrives with the profile update). */
export type PatientPhone = { phone?: string | null };

export const getOutreachCapabilities = (signal?: AbortSignal) =>
  apiFetch<OutreachCapabilities>("/outreach/capabilities", { signal });

export const textMe = (kind: OutreachTextKind = "checkin") =>
  apiFetch<OutreachTextResult>("/outreach/sms", { method: "POST", body: { kind } });

export const getTextStatus = (providerId: string, signal?: AbortSignal) =>
  apiFetch<OutreachTextStatus>(`/outreach/sms/${encodeURIComponent(providerId)}`, { signal });

export const callMe = () => apiFetch<OutreachCallResult>("/outreach/call", { method: "POST", body: { kind: "checkin" } });

/** Patient: save their own mobile number (E.164), or clear it with null. */
export const updateMyPhone = (phone: string | null) =>
  apiFetch<PatientPhone>("/patients/me", { method: "PATCH", body: { phone } });

export const getMyPhone = (signal?: AbortSignal) => apiFetch<PatientPhone>("/patients/me", { signal });
