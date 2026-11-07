import { apiFetch } from "./client";
import type { SymptomIn, SymptomOut, SymptomResult } from "./types";

export const logSymptoms = (body: SymptomIn) => apiFetch<SymptomResult>("/symptoms", { method: "POST", body });

/** Newest first. Patients omit `patientId`; clinicians must pass it. */
export const getSymptoms = (patientId?: string, signal?: AbortSignal) =>
  apiFetch<SymptomOut[]>(patientId ? `/symptoms?patient_id=${encodeURIComponent(patientId)}` : "/symptoms", {
    signal,
  });
