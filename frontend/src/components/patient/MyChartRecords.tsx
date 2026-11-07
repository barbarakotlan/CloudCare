"use client";

import { CalendarDays, FileText, FlaskConical, Pill, Stethoscope, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api/client";
import {
  getEpicRecords,
  type EpicEncounter,
  type EpicLab,
  type EpicMedication,
  type EpicNote,
  type EpicRecords,
  type EpicResourceKey,
} from "@/lib/api/epic";
import { useAsync } from "@/lib/hooks/useAsync";
import { MyChartReconciliation } from "./MyChartReconciliation";

type Tab = EpicResourceKey;

const TABS: { key: Tab; short: string; long: string; noun: string; icon: LucideIcon }[] = [
  { key: "medications", short: "Meds", long: "Medications", noun: "medications", icon: Pill },
  { key: "labs", short: "Labs", long: "Labs", noun: "lab results", icon: FlaskConical },
  { key: "encounters", short: "Visits", long: "Visits", noun: "visits", icon: Stethoscope },
  { key: "notes", short: "Notes", long: "Notes", noun: "clinical notes", icon: FileText },
];

const PAGE = 8;

type Loaded = { kind: "ok"; records: EpicRecords } | { kind: "gone" };

/** FHIR dates can be partial ("2026-11"); show those as-is instead of "Invalid Date". */
function fhirDate(value: string | null, withTime = false): string | null {
  if (!value) return null;
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const d = new Date(dateOnly ? `${value}T00:00:00` : value);
  if (Number.isNaN(d.getTime())) return value;
  return withTime && !dateOnly
    ? d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function statusTone(status: string | null): BadgeTone {
  const s = (status ?? "").toLowerCase();
  if (s === "active" || s === "final" || s === "finished" || s === "current") return "green";
  if (s === "stopped" || s === "cancelled" || s === "entered-in-error" || s === "revoked") return "red";
  if (s === "on-hold" || s === "preliminary" || s === "in-progress" || s === "draft") return "amber";
  return "gray";
}

function interpretationTone(text: string | null): BadgeTone {
  const s = (text ?? "").toLowerCase();
  if (/critical|panic|\bhh\b|\bll\b/.test(s)) return "red";
  if (/high|low|abnormal|^h$|^l$|^a$/.test(s)) return "amber";
  if (/normal|^n$/.test(s)) return "green";
  return "gray";
}

function emptyText(records: EpicRecords, tab: (typeof TABS)[number]): string {
  if (!records.missing.includes(tab.key)) return `No ${tab.noun} on file in MyChart.`;
  const reason = records.missing_reasons[tab.key];
  if (reason === "forbidden" || reason === "unauthorized") {
    return `Your health system hasn't shared ${tab.noun} with CloudCare.`;
  }
  if (reason === "not_found") return `${tab.long} aren't available from your health system.`;
  return `Couldn't load ${tab.noun} right now. Try "Refresh records" in a minute.`;
}

function Row({ title, badges, meta, children }: { title: ReactNode; badges?: ReactNode; meta?: ReactNode; children?: ReactNode }) {
  return (
    <li className="rounded-3xl bg-surface-soft p-4 ring-1 ring-line/60">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
        <h4 className="min-w-0 font-extrabold break-words text-ink">{title}</h4>
        {badges ? <div className="flex shrink-0 flex-wrap gap-1.5">{badges}</div> : null}
      </div>
      {children}
      {meta ? <p className="mt-2 text-sm text-brand-gray">{meta}</p> : null}
    </li>
  );
}

function joinMeta(parts: Array<string | null | undefined>) {
  return parts.filter(Boolean).join(" · ") || null;
}

function MedicationRow({ m }: { m: EpicMedication }) {
  return (
    <Row
      title={m.name}
      badges={m.status ? <Badge tone={statusTone(m.status)}>{m.status}</Badge> : null}
      meta={joinMeta([m.prescriber ? `Prescribed by ${m.prescriber}` : null, fhirDate(m.authored_on)])}
    >
      {m.dose_text || m.frequency_text ? (
        <p className="mt-1.5 text-[0.95rem] leading-relaxed text-ink-soft">
          {[m.dose_text, m.frequency_text && m.frequency_text !== m.dose_text ? m.frequency_text : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
      ) : null}
    </Row>
  );
}

function LabRow({ l }: { l: EpicLab }) {
  return (
    <Row
      title={l.name}
      badges={
        <>
          {l.interpretation ? <Badge tone={interpretationTone(l.interpretation)}>{l.interpretation}</Badge> : null}
          {l.status && l.status !== "final" ? <Badge tone={statusTone(l.status)}>{l.status}</Badge> : null}
        </>
      }
      meta={joinMeta([l.reference_range ? `Range ${l.reference_range}` : null, fhirDate(l.effective_at, true)])}
    >
      {l.value ? (
        <p className="mt-1.5 text-[0.95rem] leading-relaxed text-ink">
          <span className="text-lg font-extrabold">{l.value}</span>
          {l.unit ? <span className="ml-1 text-ink-soft">{l.unit}</span> : null}
        </p>
      ) : null}
    </Row>
  );
}

function EncounterRow({ e }: { e: EpicEncounter }) {
  const start = fhirDate(e.start);
  const end = fhirDate(e.end);
  return (
    <Row
      title={e.type ?? "Visit"}
      badges={e.class ? <Badge tone="pale">{e.class}</Badge> : null}
      meta={joinMeta([e.location])}
    >
      <p className="mt-1.5 flex items-center gap-1.5 text-[0.95rem] text-ink-soft">
        <CalendarDays className="size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
        {start ? (end && end !== start ? `${start} to ${end}` : start) : "Date not listed"}
      </p>
      {e.reason ? <p className="mt-1 text-[0.95rem] text-ink-soft">Reason: {e.reason}</p> : null}
    </Row>
  );
}

function NoteRow({ n }: { n: EpicNote }) {
  return (
    <Row
      title={n.title}
      badges={n.status ? <Badge tone={statusTone(n.status)}>{n.status}</Badge> : null}
      meta={joinMeta([n.type && n.type !== n.title ? n.type : null, n.author, fhirDate(n.date)])}
    >
      {n.content_preview ? (
        <>
          {/* Plain text from the API, rendered as text: React escapes it. */}
          <p className="mt-2 rounded-2xl bg-white p-3 text-[0.92rem] leading-relaxed whitespace-pre-line text-ink-soft ring-1 ring-line/60">
            {n.content_preview}
          </p>
          {!n.has_full_text ? (
            <p className="mt-1.5 text-xs text-brand-gray">Preview. Open MyChart to read the full note.</p>
          ) : null}
        </>
      ) : (
        <p className="mt-1.5 text-sm text-brand-gray">Text preview isn&rsquo;t available for this note. Open it in MyChart.</p>
      )}
    </Row>
  );
}

function RecordList({ records, tab }: { records: EpicRecords; tab: (typeof TABS)[number] }) {
  const [showAll, setShowAll] = useState(false);
  const items = records[tab.key];
  if (items.length === 0) {
    return <p className="rounded-2xl bg-surface-soft p-4 text-sm text-ink-soft">{emptyText(records, tab)}</p>;
  }
  const visible = showAll ? items : items.slice(0, PAGE);
  return (
    <>
      <ul className="grid gap-3">
        {tab.key === "medications" && (visible as EpicMedication[]).map((m, i) => <MedicationRow key={i} m={m} />)}
        {tab.key === "labs" && (visible as EpicLab[]).map((l, i) => <LabRow key={i} l={l} />)}
        {tab.key === "encounters" && (visible as EpicEncounter[]).map((e, i) => <EncounterRow key={i} e={e} />)}
        {tab.key === "notes" && (visible as EpicNote[]).map((n, i) => <NoteRow key={i} n={n} />)}
      </ul>
      {items.length > PAGE ? (
        <Button variant="ghost" size="sm" className="mt-3" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Show fewer" : `Show all ${items.length}`}
        </Button>
      ) : null}
    </>
  );
}

/**
 * Records pulled live from Epic: tabs for medications, labs, visits and notes.
 * `version` changes force a refetch; `onGone` tells the parent the connection is
 * no longer usable (revoked, expired or deleted) so it can reload the status.
 */
export function MyChartRecords({
  version,
  onGone,
  onSynced,
}: {
  version: number;
  onGone: () => void;
  onSynced?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("medications");
  const records = useAsync<Loaded>(`epic-records-${version}`, async (signal) => {
    try {
      return { kind: "ok", records: await getEpicRecords(signal) };
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 404)) return { kind: "gone" };
      throw err;
    }
  });

  const data = records.data;
  useEffect(() => {
    if (data?.kind === "gone") onGone();
    else if (data?.kind === "ok") onSynced?.();
  }, [data, onGone, onSynced]);

  if (records.loading && !data) {
    return (
      <div className="mt-5 grid gap-3" aria-busy="true" aria-label="Loading your MyChart records">
        <Skeleton className="h-11 w-full rounded-full" />
        <Skeleton className="h-20 w-full rounded-3xl" />
        <Skeleton className="h-20 w-full rounded-3xl" />
      </div>
    );
  }
  if (records.error) {
    return (
      <div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl bg-brand-red/6 p-4 ring-1 ring-brand-red/20">
        <p role="alert" className="flex-1 text-sm font-semibold text-brand-red-dark">
          Couldn&rsquo;t load your MyChart records: {records.error}
        </p>
        <Button variant="secondary" size="sm" onClick={records.reload}>
          Try again
        </Button>
      </div>
    );
  }
  if (data?.kind !== "ok") return null;

  const current = TABS.find((t) => t.key === tab) ?? TABS[0];
  return (
    <div className="mt-5" aria-busy={records.loading}>
      <MyChartReconciliation epicMedications={data.records.medications} />
      <SegmentedControl<Tab>
        label="MyChart record type"
        size="sm"
        value={tab}
        onChange={setTab}
        options={TABS.map((t) => ({
          value: t.key,
          label: (
            <>
              <span className="sm:hidden">{t.short}</span>
              <span className="hidden sm:inline">{t.long}</span>
              <span className="text-xs font-semibold text-brand-gray">{data.records[t.key].length}</span>
            </>
          ),
        }))}
      />
      <div className="mt-4" role="region" aria-label={current.long}>
        <RecordList key={current.key} records={data.records} tab={current} />
      </div>
      <p className="mt-4 text-xs text-brand-gray">
        Read-only copy fetched from MyChart {fhirDate(data.records.fetched_at, true)}. CloudCare doesn&rsquo;t keep your
        clinical records.
      </p>
    </div>
  );
}
