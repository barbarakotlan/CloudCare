import type { EscalationTrigger, RiskLevel, Severity } from "@/lib/api/types";

/** Backend datetimes from SQLite have no offset but are UTC. */
export function parseApiDate(value: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T00:00:00`);
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

/** Whole days between a YYYY-MM-DD date and `now`, local time. Day of surgery = day 0. */
export function daysSince(dateOnly: string, now: number): number {
  const start = parseApiDate(dateOnly);
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((today.getTime() - start.getTime()) / 86_400_000));
}

export function relativeTime(value: string | Date, now: number): string {
  const d = typeof value === "string" ? parseApiDate(value) : value;
  const diff = Math.round((now - d.getTime()) / 1000);
  const future = diff < 0;
  const s = Math.abs(diff);
  let out: string;
  if (s < 45) return future ? "in a moment" : "just now";
  if (s < 3600) out = `${Math.round(s / 60)} min`;
  else if (s < 86_400) out = `${Math.round(s / 3600)} h`;
  else out = `${Math.round(s / 86_400)} d`;
  return future ? `in ${out}` : `${out} ago`;
}

export function formatDate(value: string | Date, opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" }) {
  const d = typeof value === "string" ? parseApiDate(value) : value;
  return d.toLocaleDateString(undefined, opts);
}

export function formatDateTime(value: string | Date) {
  const d = typeof value === "string" ? parseApiDate(value) : value;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function formatClock(hhmm: string) {
  const [h, m] = hhmm.split(":").map(Number);
  const suffix = h >= 12 ? "PM" : "AM";
  const hour = h % 12 === 0 ? 12 : h % 12;
  return `${hour}:${String(m).padStart(2, "0")} ${suffix}`;
}

export function greetingFor(now: number) {
  const h = new Date(now).getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function firstName(fullName: string) {
  const parts = fullName.replace(/^(Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+/i, "").split(/\s+/);
  return parts[0] ?? fullName;
}

export const FACTOR_LABEL: Record<string, string> = {
  temperature_f: "Fever",
  shortness_of_breath: "Shortness of breath",
  wound_drainage: "Wound drainage",
  wound_redness: "Wound redness",
  pain_level: "Pain level",
  mobility_level: "Low mobility",
  swelling: "Swelling",
  nausea: "Nausea",
  comorbidities: "Health history",
  days_since_surgery: "Days since surgery",
  age: "Age",
  has_diabetes: "Diabetes",
  is_smoker: "Smoker",
  has_obesity: "Obesity",
  procedure_type: "Type of surgery",
  procedure_orthopedic: "Orthopedic surgery",
  procedure_abdominal: "Abdominal surgery",
  procedure_cardiac: "Heart surgery",
  procedure_general: "General surgery",
};

export function factorLabel(feature: string) {
  const label = FACTOR_LABEL[feature];
  if (label) return label;
  const words = feature.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** snake_case tokens such as `shortness_of_breath` or `temperature_f`. */
const FEATURE_TOKEN = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g;

/**
 * Server-written text names model features raw ("Top factors: shortness_of_breath,
 * temperature_f"). Swap them for the labels people read everywhere else.
 */
export function humanizeFactors(text: string): string {
  return text.replace(FEATURE_TOKEN, (token) => factorLabel(token));
}

/** Message timestamp: time only for today, date and time otherwise. */
export function formatMessageTime(value: string | Date, now: number | null = null) {
  const d = typeof value === "string" ? parseApiDate(value) : value;
  const today = new Date(now ?? Date.now());
  const sameDay =
    d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate();
  return sameDay
    ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export const RISK_LABEL: Record<RiskLevel, string> = { low: "Low risk", medium: "Medium risk", high: "High risk" };

export const SEVERITY_LABEL: Record<Severity, string> = {
  emergency: "Emergency",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const TRIGGER_LABEL: Record<EscalationTrigger, string> = {
  red_flag: "Red-flag symptom",
  high_risk: "High risk check-in",
  unanswered_question: "Question not in plan",
  patient_request: "Patient asked to contact you",
};

export const MOBILITY_LABEL = [
  "Can't get out of bed",
  "Bed to chair only",
  "A few steps with help",
  "Walking with walker",
  "Walking on my own",
] as const;
