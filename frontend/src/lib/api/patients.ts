import { apiFetch } from "./client";
import type { CarePlanIn, CarePlanOut, PatientOut, PatientRow } from "./types";

export const getMyProfile = (signal?: AbortSignal) => apiFetch<PatientOut>("/patients/me", { signal });

export const getMyCarePlan = (signal?: AbortSignal) => apiFetch<CarePlanOut | null>("/patients/me/care-plan", { signal });

/** Clinician: assigned patients, highest risk first. */
export const listPatients = (signal?: AbortSignal) => apiFetch<PatientRow[]>("/patients", { signal });

export const getPatient = (id: string, signal?: AbortSignal) =>
  apiFetch<PatientOut>(`/patients/${encodeURIComponent(id)}`, { signal });

export const uploadCarePlan = (patientId: string, body: CarePlanIn) =>
  apiFetch<CarePlanOut>(`/patients/${encodeURIComponent(patientId)}/care-plan`, { method: "POST", body });
