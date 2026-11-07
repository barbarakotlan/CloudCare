/**
 * Medication and appointment reminders.
 *
 *   GET  /patients/me/medications                 -> MedicationOut[]
 *   GET  /patients/me/medication-logs?since=<ISO> -> MedicationLogOut[]
 *   POST /medications/{id}/logs                   -> MedicationLogOut (taken / skipped; re-posting updates)
 *   GET  /patients/me/appointments                -> AppointmentOut[] (all, soonest first)
 *
 * Dose times are "HH:MM" in the patient's local time. The backend stores and
 * returns dose times in UTC, so doses and logs are matched by UTC milliseconds.
 */

import { parseApiDate } from "@/lib/format";
import { apiFetch } from "./client";
import type {
  AppointmentOut,
  MedicationLogIn,
  MedicationLogOut,
  MedicationLogStatus,
  MedicationOut,
} from "./types";

export type Medication = MedicationOut;
export type MedicationLog = MedicationLogOut;
export type Appointment = AppointmentOut;
export type { MedicationLogStatus };

/** One scheduled dose for today, derived from a medication and its log (if any). */
export type Dose = {
  /** Stable id: medication id + UTC ms of the dose time. */
  key: string;
  medication: Medication;
  /** "HH:MM" local. */
  time: string;
  /** Local dose time as ISO with the local offset, e.g. 2026-11-07T08:00:00-05:00. */
  scheduled_for: string;
  /** Dose time in UTC ms. */
  at: number;
  status: MedicationLogStatus;
};

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const getMyMedications = (signal?: AbortSignal) =>
  apiFetch<Medication[]>("/patients/me/medications", { signal });

/** Logs for doses scheduled at or after `since` (pass local midnight for today). */
export const getMyMedicationLogs = (since: Date, signal?: AbortSignal) =>
  apiFetch<MedicationLog[]>(`/patients/me/medication-logs?since=${encodeURIComponent(toOffsetIso(since))}`, {
    signal,
  });

export const logMedication = (medicationId: string, scheduledFor: string, status: MedicationLogIn["status"]) =>
  apiFetch<MedicationLog>(`/medications/${encodeURIComponent(medicationId)}/logs`, {
    method: "POST",
    body: { scheduled_for: scheduledFor, status } satisfies MedicationLogIn,
  });

export const getMyAppointments = (signal?: AbortSignal) =>
  apiFetch<Appointment[]>("/patients/me/appointments", { signal });

// ---------------------------------------------------------------------------
// Local-time helpers
// ---------------------------------------------------------------------------

const pad = (n: number) => String(n).padStart(2, "0");

/** YYYY-MM-DD for the local calendar day of `ms`. */
export function localDayKey(ms: number): string {
  const d = new Date(ms);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Local midnight of a YYYY-MM-DD day key. */
export function startOfLocalDay(dayKey: string): Date {
  const [y, m, d] = dayKey.split("-").map(Number);
  return new Date(y, m - 1, d, 0, 0, 0, 0);
}

/** ISO string in local time with its UTC offset, e.g. 2026-11-07T08:00:00-05:00. */
export function toOffsetIso(d: Date): string {
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const abs = Math.abs(offset);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  );
}

const HHMM = /^([01]?\d|2[0-3]):([0-5]\d)$/;

/** True when the medication is active on the given local day. */
function activeOn(med: Medication, dayKey: string): boolean {
  if (!med.is_active) return false;
  if (med.start_date && med.start_date > dayKey) return false;
  if (med.end_date && med.end_date < dayKey) return false;
  return true;
}

export function logKey(medicationId: string, scheduledFor: string): string {
  return `${medicationId}@${parseApiDate(scheduledFor).getTime()}`;
}

/** Today's scheduled doses (sorted by time), with status taken from the logs. */
export function buildDoses(meds: Medication[], logs: MedicationLog[], dayKey: string): Dose[] {
  const statusByKey = new Map(logs.map((l) => [logKey(l.medication_id, l.scheduled_for), l.status]));
  const day = startOfLocalDay(dayKey);
  const doses: Dose[] = [];
  for (const med of meds) {
    if (!activeOn(med, dayKey)) continue;
    for (const time of new Set(med.times_of_day)) {
      const match = HHMM.exec(time);
      if (!match) continue;
      const when = new Date(day);
      when.setHours(Number(match[1]), Number(match[2]), 0, 0);
      const key = `${med.id}@${when.getTime()}`;
      doses.push({
        key,
        medication: med,
        time: `${pad(Number(match[1]))}:${match[2]}`,
        scheduled_for: toOffsetIso(when),
        at: when.getTime(),
        status: statusByKey.get(key) ?? "pending",
      });
    }
  }
  return doses.sort((a, b) => a.at - b.at || a.medication.name.localeCompare(b.medication.name));
}

/** "As needed" medications (no fixed times) active today. */
export function asNeededMedications(meds: Medication[], dayKey: string): Medication[] {
  return meds.filter((m) => m.times_of_day.length === 0 && activeOn(m, dayKey));
}

/** Scheduled appointments at or after `now`, soonest first. */
export function upcomingAppointments(appts: Appointment[], now: number): Appointment[] {
  return appts
    .filter((a) => a.status === "scheduled" && parseApiDate(a.scheduled_at).getTime() >= now)
    .sort((a, b) => parseApiDate(a.scheduled_at).getTime() - parseApiDate(b.scheduled_at).getTime());
}
