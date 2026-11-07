/**
 * Medication and appointment reminders: TYPED MOCK DATA.
 *
 * TODO(Barbara): the tables exist in database/scheme.sql (medications,
 * medication_logs, appointments) but the backend has no routes yet. Once
 * these ship, replace the bodies below with apiFetch calls and delete the
 * mock data. Nothing else in the UI needs to change:
 *   GET  /patients/me/medications      -> Medication[]
 *   POST /medications/{id}/logs        -> MedicationLog   (mark taken / skipped)
 *   GET  /patients/me/appointments     -> Appointment[]
 */

export type Medication = {
  id: string;
  name: string;
  dosage: string;
  instructions: string | null;
  /** "HH:MM" local times. Empty = as needed. */
  times_of_day: string[];
  start_date: string;
  end_date: string | null;
  is_active: boolean;
};

export type MedicationLogStatus = "pending" | "taken" | "skipped" | "missed";

export type MedicationLog = {
  id: string;
  medication_id: string;
  scheduled_for: string;
  status: MedicationLogStatus;
  responded_at: string | null;
};

export type Appointment = {
  id: string;
  title: string;
  provider_name: string | null;
  location: string | null;
  scheduled_at: string;
  status: "scheduled" | "completed" | "missed" | "cancelled";
  notes: string | null;
};

/** One scheduled dose for today, derived from a medication + its log. */
export type Dose = { medication: Medication; time: string; scheduled_for: string; status: MedicationLogStatus };

// ---------------------------------------------------------------------------
// Mock data (matches the "Medications" section of the seeded care plan)
// ---------------------------------------------------------------------------

const MOCK_MEDICATIONS: Medication[] = [
  {
    id: "med-acetaminophen",
    name: "Acetaminophen",
    dosage: "1000 mg",
    instructions: "Every 8 hours.",
    times_of_day: ["06:00", "14:00", "22:00"],
    start_date: "2026-11-04",
    end_date: null,
    is_active: true,
  },
  {
    id: "med-aspirin",
    name: "Aspirin",
    dosage: "81 mg",
    instructions: "Twice daily for 4 weeks to prevent blood clots.",
    times_of_day: ["08:00", "20:00"],
    start_date: "2026-11-04",
    end_date: "2026-12-02",
    is_active: true,
  },
  {
    id: "med-oxycodone",
    name: "Oxycodone",
    dosage: "5 mg",
    instructions: "Only as needed for severe pain. No driving while taking it.",
    times_of_day: [],
    start_date: "2026-11-04",
    end_date: null,
    is_active: true,
  },
];

const LOG_KEY = "cloudcare.mock.medlogs";

function readLogs(): Record<string, MedicationLog> {
  try {
    const raw = window.localStorage.getItem(LOG_KEY);
    return raw ? (JSON.parse(raw) as Record<string, MedicationLog>) : {};
  } catch {
    return {};
  }
}

function writeLogs(logs: Record<string, MedicationLog>) {
  try {
    window.localStorage.setItem(LOG_KEY, JSON.stringify(logs));
  } catch {
    // Storage unavailable (private mode): state still lives in the component.
  }
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function localDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function atLocalTime(base: Date, hhmm: string): Date {
  const [h, m] = hhmm.split(":").map(Number);
  const d = new Date(base);
  d.setHours(h, m, 0, 0);
  return d;
}

// ---------------------------------------------------------------------------
// API surface (swap these for real routes)
// ---------------------------------------------------------------------------

export async function getMyMedications(): Promise<Medication[]> {
  await delay(250);
  return MOCK_MEDICATIONS.filter((m) => m.is_active);
}

/** Today's scheduled doses with their taken/skipped status. */
export async function getTodaysDoses(now: Date = new Date()): Promise<Dose[]> {
  const meds = await getMyMedications();
  const logs = readLogs();
  const doses: Dose[] = [];
  for (const med of meds) {
    for (const time of med.times_of_day) {
      const scheduled = atLocalTime(now, time);
      const key = `${med.id}@${localDateKey(now)}T${time}`;
      const log = logs[key];
      doses.push({
        medication: med,
        time,
        scheduled_for: scheduled.toISOString(),
        status: log?.status ?? "pending",
      });
    }
  }
  return doses.sort((a, b) => a.time.localeCompare(b.time));
}

export async function logMedication(
  medicationId: string,
  scheduledFor: string,
  status: Exclude<MedicationLogStatus, "pending">,
): Promise<MedicationLog> {
  await delay(200);
  const when = new Date(scheduledFor);
  const time = `${String(when.getHours()).padStart(2, "0")}:${String(when.getMinutes()).padStart(2, "0")}`;
  const key = `${medicationId}@${localDateKey(when)}T${time}`;
  const log: MedicationLog = {
    id: key,
    medication_id: medicationId,
    scheduled_for: scheduledFor,
    status,
    responded_at: new Date().toISOString(),
  };
  const logs = readLogs();
  logs[key] = log;
  writeLogs(logs);
  return log;
}

export async function getMyAppointments(surgeryDate?: string, now: Date = new Date()): Promise<Appointment[]> {
  await delay(250);
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(10, 30, 0, 0);

  const followUp = surgeryDate ? new Date(`${surgeryDate}T09:00:00`) : new Date(now);
  followUp.setDate(followUp.getDate() + 14);
  if (!surgeryDate) followUp.setHours(9, 0, 0, 0);

  return [
    {
      id: "appt-pt",
      title: "Physical therapy",
      provider_name: "Sam Rivera, PT",
      location: "Outpatient Rehab, Building B",
      scheduled_at: tomorrow.toISOString(),
      status: "scheduled",
      notes: "Bring your walker and wear loose shorts.",
    },
    {
      id: "appt-followup",
      title: "Post-op follow-up",
      provider_name: "Dr. Priya Patel",
      location: "Orthopedic Clinic, 3rd floor",
      scheduled_at: followUp.toISOString(),
      status: "scheduled",
      notes: "Incision check and staple removal.",
    },
  ];
}
