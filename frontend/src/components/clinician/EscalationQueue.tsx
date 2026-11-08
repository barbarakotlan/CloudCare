"use client";

import { BellRing, CheckCheck, Eye, Inbox, LoaderCircle, MessageSquareShare, RotateCcw, Siren } from "lucide-react";
import { useId, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Skeleton } from "@/components/ui/Skeleton";
import type { EscalationOut, EscalationStatus, EscalationTrigger, Severity } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import {
  formatDateTime,
  formatMessageTime,
  humanizeFactors,
  relativeTime,
  SEVERITY_LABEL,
  TRIGGER_LABEL,
} from "@/lib/format";
import { SEVERITY_BAR, SEVERITY_TONE, STATUS_LABEL, STATUS_TONE, TRIGGER_TONE } from "./severity";

/**
 * lg and up: a panel is capped to the viewport under the 4rem app header (plus breathing
 * room) and lays out as a column, so the page stops growing with list length.
 */
export const PANEL_LG = "lg:flex lg:max-h-[calc(100dvh-6rem)] lg:flex-col lg:overflow-hidden";
/** The part of a panel that scrolls on lg+: thin, quiet scrollbar; scrolling never chains to the page. */
export const PANEL_SCROLL =
  "lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overscroll-contain lg:[scrollbar-color:var(--line)_transparent] lg:[scrollbar-width:thin]";

export type QueueFilter = "active" | "resolved" | "all";
export type SeverityFilter = Severity | "all";

const SEVERITY_OPTIONS: Array<{ value: SeverityFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "emergency", label: "Emergency" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export function EscalationQueue({
  items,
  loading,
  error,
  filter,
  onFilter,
  severity,
  onSeverity,
  narrowed = false,
  onUpdate,
  onOpenPatient,
  highlightIds,
  now,
  lastUpdated,
}: {
  items: EscalationOut[] | undefined;
  loading: boolean;
  error: string | null;
  filter: QueueFilter;
  onFilter: (f: QueueFilter) => void;
  severity: SeverityFilter;
  onSeverity: (s: SeverityFilter) => void;
  /** A search or severity filter is hiding some items. */
  narrowed?: boolean;
  onUpdate: (id: string, status: EscalationStatus, notes?: string) => Promise<void>;
  onOpenPatient: (patientId: string) => void;
  highlightIds: Set<string>;
  now: number | null;
  lastUpdated: number | null;
}) {
  return (
    <Card aria-labelledby="queue-title" flush className={cn("min-w-0", PANEL_LG)}>
      {/* Header and filters stay put; on lg+ only the list below scrolls. */}
      <div className="p-5 pb-0 sm:p-6 sm:pb-0 lg:shrink-0 lg:border-b lg:border-line/60">
        <CardHeader
          id="queue-title"
          icon={<BellRing className="size-5" aria-hidden="true" />}
          title="Escalation queue"
          description={
            <span className="inline-flex items-center gap-1.5">
              <span className="relative flex size-2" aria-hidden="true">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-ok opacity-60 motion-reduce:hidden" />
                <span className="relative inline-flex size-2 rounded-full bg-ok" />
              </span>
              Live · refreshes every 5 s
              {lastUpdated !== null && now !== null ? ` · updated ${relativeTime(new Date(lastUpdated), now)}` : ""}
            </span>
          }
          className="flex-wrap"
          action={
            <SegmentedControl<QueueFilter>
              label="Show escalations"
              size="sm"
              value={filter}
              onChange={onFilter}
              fullWidth={false}
              options={[
                { value: "active", label: "Active" },
                { value: "resolved", label: "Resolved" },
                { value: "all", label: "All" },
              ]}
            />
          }
        />
        {/* Five options don't fit a phone: the row scrolls sideways inside the card. */}
        <div className="-mx-5 mb-2 overflow-x-auto px-5 [scrollbar-width:none] sm:-mx-6 sm:px-6 [&::-webkit-scrollbar]:hidden">
          <SegmentedControl<SeverityFilter>
            label="Severity"
            size="sm"
            value={severity}
            onChange={onSeverity}
            fullWidth={false}
            className="min-w-max"
            options={SEVERITY_OPTIONS}
          />
        </div>
      </div>

      <div className={PANEL_SCROLL}>
        {error ? (
          <p role="alert" className="mx-5 mt-3 mb-4 rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark sm:mx-6">
            {error}
          </p>
        ) : null}

        {loading && !items ? (
          <div className="flex flex-col gap-3 p-5 sm:p-6">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        ) : null}

        {items && items.length === 0 ? (
          <div className="flex flex-col items-center px-6 py-12 text-center">
            <span className="grid size-14 place-items-center rounded-full bg-surface-pale text-brand-cyan-strong">
              <Inbox className="size-7" aria-hidden="true" />
            </span>
            <p className="mt-4 font-extrabold text-ink">
              {narrowed
                ? "No escalations match these filters"
                : filter === "active"
                  ? "Nothing needs you right now"
                  : "No escalations here yet"}
            </p>
            <p className="mt-1 max-w-sm text-sm text-brand-gray">
              {narrowed
                ? "Clear the search or pick another severity to see the rest."
                : "Red-flag messages, high-risk check-ins and patients asking to contact you will appear here within seconds."}
            </p>
          </div>
        ) : null}

        {items && items.length > 0 ? (
          <ul className="flex flex-col gap-3 p-4 sm:p-6 sm:pt-2 lg:pt-4" aria-label="Escalations, most urgent first">
            {items.map((e) => (
              <EscalationItem
                key={e.id}
                item={e}
                now={now}
                highlight={highlightIds.has(e.id)}
                onUpdate={onUpdate}
                onOpenPatient={onOpenPatient}
              />
            ))}
          </ul>
        ) : null}
      </div>
    </Card>
  );
}

export function TriggerLabel({ trigger }: { trigger: EscalationTrigger }) {
  const label = TRIGGER_LABEL[trigger] ?? trigger;
  const tone = TRIGGER_TONE[trigger];
  if (tone) {
    return (
      <Badge tone={tone}>
        <MessageSquareShare className="size-3.5" aria-hidden="true" />
        {label}
      </Badge>
    );
  }
  return <span className="text-sm font-bold text-ink-soft">{label}</span>;
}

/**
 * "Acknowledged by Dr. X · 3:12 PM" / "Resolved by Dr. X · Nov 7, 3:12 PM".
 * Older servers send no reviewer or acknowledge time; show what is known.
 */
export function reviewText(item: EscalationOut): string | null {
  const by = item.reviewed_by_name ? ` by ${item.reviewed_by_name}` : "";
  if (item.status === "resolved") {
    if (!item.resolved_at && !by) return null;
    return `Resolved${by}${item.resolved_at ? ` · ${formatMessageTime(item.resolved_at)}` : ""}`;
  }
  if (item.status === "acknowledged") {
    if (!item.acknowledged_at && !by) return null;
    return `Acknowledged${by}${item.acknowledged_at ? ` · ${formatMessageTime(item.acknowledged_at)}` : ""}`;
  }
  return null;
}

function ReviewLine({ item }: { item: EscalationOut }) {
  const text = reviewText(item);
  if (!text) return null;
  return (
    <p className="mt-1.5 flex items-center gap-1.5 text-xs font-semibold text-brand-gray">
      <CheckCheck className="size-3.5 shrink-0" aria-hidden="true" />
      <span className="min-w-0 break-words">{text}</span>
    </p>
  );
}

function EscalationItem({
  item,
  now,
  highlight,
  onUpdate,
  onOpenPatient,
}: {
  item: EscalationOut;
  now: number | null;
  highlight: boolean;
  onUpdate: (id: string, status: EscalationStatus, notes?: string) => Promise<void>;
  onOpenPatient: (patientId: string) => void;
}) {
  const [busy, setBusy] = useState<EscalationStatus | null>(null);
  const [resolving, setResolving] = useState(false);
  const [notes, setNotes] = useState("");
  const notesId = useId();
  const emergency = item.severity === "emergency";

  async function act(status: EscalationStatus, withNotes?: string) {
    setBusy(status);
    try {
      await onUpdate(item.id, status, withNotes);
      setResolving(false);
    } finally {
      setBusy(null);
    }
  }

  return (
    <li
      className={cn(
        "relative overflow-hidden rounded-3xl bg-white py-4 pr-4 pl-6 ring-1 sm:pr-5",
        emergency && item.status !== "resolved" ? "bg-[#fff6f7] ring-brand-red/30" : "ring-line",
        item.status === "resolved" && "opacity-75",
        highlight && "animate-flash",
      )}
    >
      <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-1.5", SEVERITY_BAR[item.severity])} />
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={SEVERITY_TONE[item.severity]} dot>
          {emergency ? <Siren className="size-3.5" aria-hidden="true" /> : null}
          {SEVERITY_LABEL[item.severity]}
        </Badge>
        <TriggerLabel trigger={item.trigger_type} />
        <Badge tone={STATUS_TONE[item.status]} className="ml-auto">
          {STATUS_LABEL[item.status]}
        </Badge>
      </div>

      <div className="mt-2 flex min-w-0 flex-wrap items-baseline gap-x-2">
        <button
          type="button"
          onClick={() => onOpenPatient(item.patient_id)}
          className="min-w-0 rounded-md text-left text-lg font-extrabold break-words text-ink underline-offset-4 hover:text-brand-cyan-strong hover:underline"
        >
          {item.patient_name}
        </button>
        <span className="text-sm text-brand-gray" title={formatDateTime(item.created_at)}>
          {now !== null ? relativeTime(item.created_at, now) : formatDateTime(item.created_at)}
        </span>
      </div>
      <p className="mt-1 leading-relaxed break-words text-ink-soft">{humanizeFactors(item.summary)}</p>
      <ReviewLine item={item} />
      {item.clinician_notes ? (
        <p className="mt-2 rounded-2xl bg-surface-soft px-3 py-2 text-sm break-words text-ink-soft">
          <span className="font-bold text-ink">Note: </span>
          {item.clinician_notes}
        </p>
      ) : null}

      {resolving ? (
        <div className="mt-3 flex flex-col gap-2">
          <label htmlFor={notesId} className="text-sm font-bold text-ink-soft">
            Resolution note (optional)
          </label>
          <Textarea
            id={notesId}
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Called patient, advised to keep icing. Follow-up tomorrow."
            autoFocus
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void act("resolved", notes.trim() || undefined)} disabled={busy !== null}>
              {busy === "resolved" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <CheckCheck className="size-4" aria-hidden="true" />}
              Confirm resolve
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setResolving(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {item.status === "open" ? (
            <Button size="sm" variant="secondary" onClick={() => void act("acknowledged")} disabled={busy !== null}>
              {busy === "acknowledged" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
              Acknowledge
            </Button>
          ) : null}
          {item.status !== "resolved" ? (
            <Button size="sm" onClick={() => setResolving(true)} disabled={busy !== null}>
              <CheckCheck className="size-4" aria-hidden="true" />
              Resolve
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => void act("open")} disabled={busy !== null}>
              <RotateCcw className="size-4" aria-hidden="true" />
              Reopen
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => onOpenPatient(item.patient_id)}>
            View patient
          </Button>
        </div>
      )}
    </li>
  );
}
