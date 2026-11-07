import { apiFetch } from "./client";
import type { CarePlanIn, CarePlanOut, PatientOut, PatientRow, PatientUpdate } from "./types";

export const getMyProfile = (signal?: AbortSignal) => apiFetch<PatientOut>("/patients/me", { signal });

export const getMyCarePlan = (signal?: AbortSignal) => apiFetch<CarePlanOut | null>("/patients/me/care-plan", { signal });

/** Clinician: assigned patients, highest risk first. */
export const listPatients = (signal?: AbortSignal) => apiFetch<PatientRow[]>("/patients", { signal });

export const getPatient = (id: string, signal?: AbortSignal) =>
  apiFetch<PatientOut>(`/patients/${encodeURIComponent(id)}`, { signal });

/** Clinician: the patient's active care plan, or null when none has been uploaded. */
export const getPatientCarePlan = (id: string, signal?: AbortSignal) =>
  apiFetch<CarePlanOut | null>(`/patients/${encodeURIComponent(id)}/care-plan`, { signal });

/** Clinician: edit the patient's profile (e.g. finish "Pending clinician setup"). */
export const updatePatient = (id: string, body: PatientUpdate) =>
  apiFetch<PatientOut>(`/patients/${encodeURIComponent(id)}`, { method: "PATCH", body });

export const uploadCarePlan = (patientId: string, body: CarePlanIn) =>
  apiFetch<CarePlanOut>(`/patients/${encodeURIComponent(patientId)}/care-plan`, { method: "POST", body });
