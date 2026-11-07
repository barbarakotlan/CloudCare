import { apiFetch } from "./client";
import type { EscalationFilter, EscalationOut, EscalationUpdate } from "./types";

/** Clinician queue, most urgent first. Default `active` = open + acknowledged. */
export const listEscalations = (status: EscalationFilter = "active", signal?: AbortSignal) =>
  apiFetch<EscalationOut[]>(`/escalations?status=${status}`, { signal });

export const updateEscalation = (id: string, body: EscalationUpdate) =>
  apiFetch<EscalationOut>(`/escalations/${encodeURIComponent(id)}`, { method: "PATCH", body });
