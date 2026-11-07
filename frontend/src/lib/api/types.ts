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
};

export type PatientOut = {
  id: string;
  full_name: string;
  procedure_name: string;
  procedure_type: string;
  surgery_date: string;
  discharge_date: string | null;
  comorbidities: string[];
};

export type CarePlanChunk = { id: string; chunk_index: number; section: string | null; content: string };

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

export type ChatMessageOut = {
  id: string;
  role: ChatRole;
  content: string;
  citations: Citation[];
  answered_from_plan: boolean | null;
  red_flag: boolean;
  created_at: string;
};

export type ChatReply = { message: ChatMessageOut; escalated: boolean };

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
};

export type EscalationUpdate = { status: EscalationStatus; clinician_notes?: string | null };

export type HealthOut = { status: string; database: string };
