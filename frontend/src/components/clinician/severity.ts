import type { BadgeTone } from "@/components/ui/Badge";
import type { EscalationStatus, EscalationTrigger, RiskLevel, Severity } from "@/lib/api/types";

/** Triggers shown as a badge next to severity; the rest render as plain text. */
export const TRIGGER_TONE: Partial<Record<EscalationTrigger, BadgeTone>> = {
  patient_request: "cyan",
};

export const SEVERITY_TONE: Record<Severity, BadgeTone> = {
  emergency: "red",
  high: "orange",
  medium: "amber",
  low: "gray",
};

export const SEVERITY_BAR: Record<Severity, string> = {
  emergency: "bg-sev-emergency",
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
};

export const RISK_TONE: Record<RiskLevel, BadgeTone> = { low: "green", medium: "amber", high: "red" };

export const STATUS_TONE: Record<EscalationStatus, BadgeTone> = {
  open: "cyan",
  acknowledged: "pale",
  resolved: "green",
};

export const STATUS_LABEL: Record<EscalationStatus, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};
