/**
 * Mirrors backend/app/schemas.py. Dates arrive as ISO strings; the SQLite
 * backend omits the timezone on datetimes (they are UTC), so always parse
 * them with `parseApiDate` from lib/format.ts.
 */

export type Role = "patient" | "clinician";

export type UserOut = { id: string; full_name: string; role: Role };

export type LoginResponse = { access_token: string; user: UserOut };

export type RiskLevel = "low" | "medium" | "high";

export type RiskFactor = { feature: string; impact: number };

export type RiskOut = {
  score: number;
  risk_level: RiskLevel;
  top_factors: RiskFactor[];
  model_version: string;
  created_at: string;
};

export type PatientRow = {
  id: string;
  full_name: string;
  procedure_name: string;
  surgery_date: string;
  latest_risk: RiskOut | null;
  open_escalations: number;
  last_checkin_at: string | null;
  /** Open (not resolved) escalations with severity "emergency". Older servers omit it. */
  open_emergencies?: number;
  /** Open (not resolved) escalations with severity "high". Older servers omit it. */
  open_high?: number;
  /** When the latest risk score was computed (the check-in it came from). */
  latest_risk_at?: string | null;
  last_alert_at?: string | null;
};

export type PatientOut = {
  id: string;
  full_name: string;
  procedure_name: string;
  procedure_type: string;
  surgery_date: string;
  discharge_date: string | null;
  comorbidities: string[];
  /** Mobile number in E.164 (e.g. +15551234567), or null when none is on file. */
  phone: string | null;
};

export type ProcedureType = "orthopedic" | "abdominal" | "cardiac" | "spine" | "other";

/** Clinician edit of a patient profile; only the fields sent change. Dates are YYYY-MM-DD. */
export type PatientUpdate = {
  procedure_name?: string;
  procedure_type?: ProcedureType | string;
  surgery_date?: string;
  discharge_date?: string | null;
  date_of_birth?: string | null;
  comorbidities?: string[];
  /** E.164; null clears it. */
  phone?: string | null;
};

/** Placeholder procedure the backend gives a patient who signed up before their care team set them up. */
export const PENDING_SETUP_PROCEDURE = "Pending clinician setup";

export type CarePlanChunk ={ id: string; chunk_index: number; section: string | null; content: string };

export type CarePlanOut = {
  id: string;
  title: string;
  raw_text: string;
  created_at: string;
  chunks: CarePlanChunk[];
};

export type CarePlanIn = { title: string; raw_text: string };

export type SymptomSource = "checkin" | "chat" | "voice";

export type SymptomIn = {
  pain_level: number;
  temperature_f?: number | null;
  wound_redness: boolean;
  wound_drainage: boolean;
  swelling: boolean;
  nausea: boolean;
  shortness_of_breath: boolean;
  mobility_level: number;
  free_text?: string | null;
  source: SymptomSource;
};

export type SymptomOut = {
  id: string;
  logged_at: string;
  source: string;
  pain_level: number | null;
  temperature_f: number | null;
  wound_redness: boolean;
  wound_drainage: boolean;
  swelling: boolean;
  nausea: boolean;
  shortness_of_breath: boolean;
  mobility_level: number | null;
  free_text: string | null;
};

export type SymptomResult = { symptom_log_id: string; risk: RiskOut; escalated: boolean };

export type Citation = { chunk_id: string; section: string };

export type ChatRole = "patient" | "assistant" | "clinician";

/** How Foggy handled a turn (care-team contact policy). */
export type ChatRoute =
  | "ANSWER_FROM_PLAN"
  | "NOT_IN_PLAN"
  | "REFUSE_DOSE_CHANGE"
  | "EMERGENCY_911"
  | "START_CHECKIN"
  | "CALL_SURGEON"
  | "OPERATIONAL";

export type ChatMessageOut = {
  id: string;
  role: ChatRole;
  content: string;
  citations: Citation[];
  answered_from_plan: boolean | null;
  red_flag: boolean;
  created_at: string;
  /** Present on assistant messages from backends that route replies; absent on older ones. */
  route?: ChatRoute | null;
};

export type ChatSource = "chat" | "voice";

export type ChatIn = { message: string; source?: ChatSource };

/** An action Foggy offered and is waiting for the patient to agree to. */
export type PendingAction = { kind: "message_care_team"; recipient: "care_team"; reason: string };

/** What actually happened to an action this turn. Only "sent" means a real message was queued. */
export type ActionResult = { kind: string; status: "sent" | "failed" | "simulated"; detail?: string | null };

export type CheckinStep = 1 | 2 | 3 | 4 | "done";

export type CheckinState = { step: CheckinStep; answers: Record<string, unknown> };

export type ChatReply = {
  message: ChatMessageOut;
  route?: ChatRoute | null;
  /** Foggy asked whether to contact the care team; show the yes / no quick replies. */
  offer_contact?: boolean;
  pending_action?: PendingAction | null;
  action_result?: ActionResult | null;
  checkin?: CheckinState | null;
  /** True only when a real escalation row was created this turn. */
  escalated: boolean;
};

export type ChatCapabilities = {
  message_care_team: boolean;
  call_care_team: boolean;
  emergency_call_assist: boolean;
  simulated: boolean;
};

export type EscalationTrigger = "red_flag" | "high_risk" | "unanswered_question" | "patient_request";
export type Severity = "low" | "medium" | "high" | "emergency";
export type EscalationStatus = "open" | "acknowledged" | "resolved";
export type EscalationFilter = EscalationStatus | "active" | "all";

export type EscalationOut = {
  id: string;
  patient_id: string;
  patient_name: string;
  trigger_type: EscalationTrigger;
  severity: Severity;
  summary: string;
  status: EscalationStatus;
  clinician_notes: string | null;
  created_at: string;
  resolved_at: string | null;
  /** Who last acknowledged or resolved it. Older servers omit it. */
  reviewed_by_name?: string | null;
  acknowledged_at?: string | null;
};

export type EscalationUpdate = { status: EscalationStatus; clinician_notes?: string | null };

export type MedicationOut = {
  id: string;
  name: string;
  dosage: string;
  instructions: string | null;
  /** "HH:MM" in the patient's local time. Empty = as needed. */
  times_of_day: string[];
  /** YYYY-MM-DD */
  start_date: string;
  /** YYYY-MM-DD */
  end_date: string | null;
  is_active: boolean;
};

export type MedicationLogStatus = "pending" | "taken" | "skipped" | "missed";

export type MedicationLogIn = {
  /** The dose time being answered, ISO with offset (e.g. today 08:00 local). */
  scheduled_for: string;
  /** "pending" undoes an earlier taken / skipped answer. */
  status: "taken" | "skipped" | "pending";
};

export type MedicationLogOut = {
  id: string;
  medication_id: string;
  /** UTC ISO. */
  scheduled_for: string;
  status: MedicationLogStatus;
  responded_at: string | null;
};

export type AppointmentStatus = "scheduled" | "completed" | "missed" | "cancelled";

export type AppointmentOut = {
  id: string;
  title: string;
  provider_name: string | null;
  location: string | null;
  /** UTC ISO. */
  scheduled_at: string;
  status: AppointmentStatus;
  notes: string | null;
};

export type HealthOut = { status: string; database: string };
