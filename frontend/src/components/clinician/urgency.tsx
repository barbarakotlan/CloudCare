import { Siren } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import type { EscalationOut, PatientRow, RiskLevel } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatRiskPercent, relativeTime, RISK_LABEL } from "@/lib/format";

/**
 * Two different questions, kept apart on purpose:
 *  - Current status: what is open right now (real escalations a person has to close).
 *  - Risk model: what the model scored at the last check-in (an estimate with a timestamp).
 */

export type Urgency = { emergencies: number; high: number; open: number };

/**
 * Open emergency / high counts for a patient. Newer servers send them on the row;
 * otherwise they are counted from the active escalations the dashboard already has.
 */
export function urgencyOf(row: PatientRow, active: EscalationOut[] | undefined): Urgency {
  const mine = (active ?? []).filter((e) => e.patient_id === row.id && e.status !== "resolved");
  return {
    emergencies: row.open_emergencies ?? mine.filter((e) => e.severity === "emergency").length,
    high: row.open_high ?? mine.filter((e) => e.severity === "high").length,
    open: Math.max(row.open_escalations, mine.length),
  };
}

/** When the latest risk score was computed. */
export function riskTimeOf(row: PatientRow): string | null {
  return row.latest_risk_at ?? row.latest_risk?.created_at ?? null;
}

/**
 * Worklist order: open emergencies, then open high alerts, then model risk.
 * Servers that send the counts already return rows in this order; keep theirs.
 */
export function sortWorklist(rows: PatientRow[], active: EscalationOut[] | undefined): PatientRow[] {
  if (rows.length > 0 && rows.every((r) => typeof r.open_emergencies === "number")) return rows;
  const keyed = rows.map((row) => ({ row, u: urgencyOf(row, active) }));
  keyed.sort(
    (a, b) =>
      b.u.emergencies - a.u.emergencies ||
      b.u.high - a.u.high ||
      (b.row.latest_risk?.score ?? -1) - (a.row.latest_risk?.score ?? -1),
  );
  return keyed.map((k) => k.row);
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

export function CurrentStatusChip({ urgency, className }: { urgency: Urgency; className?: string }) {
  if (urgency.emergencies > 0) {
    return (
      <Badge tone="red" className={className}>
        <Siren className="size-3.5" aria-hidden="true" />
        {urgency.emergencies} emergency open
      </Badge>
    );
  }
  if (urgency.high > 0) {
    return (
      <Badge tone="orange" dot className={className}>
        {urgency.high} high {plural(urgency.high, "alert", "alerts")}
      </Badge>
    );
  }
  return (
    <Badge tone="gray" className={className}>
      {urgency.open > 0 ? `${urgency.open} open ${plural(urgency.open, "alert", "alerts")}` : "No open alerts"}
    </Badge>
  );
}

const RISK_DOT: Record<RiskLevel, string> = { low: "bg-ok", medium: "bg-sev-medium", high: "bg-brand-red" };

/** Muted model output: level, score and when it was scored. */
export function RiskModelSummary({
  row,
  now,
  info,
  className,
  stacked = false,
}: {
  row: PatientRow;
  now: number | null;
  /** Optional explainer (info icon) rendered after the score. */
  info?: ReactNode;
  className?: string;
  /** Put the timestamp on its own line (table cells). */
  stacked?: boolean;
}) {
  const risk = row.latest_risk;
  if (!risk) {
    return <span className={cn("text-xs font-semibold text-brand-gray", className)}>No check-ins scored</span>;
  }
  const at = riskTimeOf(row);
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-brand-gray", className)}>
      <span className="inline-flex items-center gap-1.5 font-bold whitespace-nowrap text-ink-soft">
        <span aria-hidden="true" className={cn("size-1.5 rounded-full", RISK_DOT[risk.risk_level])} />
        {RISK_LABEL[risk.risk_level]} · <span className="tabular-nums">{formatRiskPercent(risk.score)}</span>
      </span>
      {info}
      {at ? (
        <span className={cn("whitespace-nowrap", stacked && "basis-full")}>
          from check-in {now !== null ? relativeTime(at, now) : ""}
        </span>
      ) : null}
    </span>
  );
}
