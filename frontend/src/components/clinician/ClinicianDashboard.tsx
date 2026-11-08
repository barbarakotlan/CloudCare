"use client";

import { AlertOctagon, BellRing, HeartPulse, Search, UsersRound } from "lucide-react";
import { useCallback, useRef, useState, type ReactNode } from "react";
import { AppHeader } from "@/components/app/AppHeader";
import { DemoResetControl, describeReset } from "@/components/app/DemoResetControl";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { ToastViewport, useToasts } from "@/components/ui/Toast";
import { errorMessage } from "@/lib/api/client";
import type { DemoResetOut } from "@/lib/api/demo";
import { listEscalations, updateEscalation } from "@/lib/api/escalations";
import { listPatients } from "@/lib/api/patients";
import type { EscalationOut, EscalationStatus, PatientOut, PatientRow } from "@/lib/api/types";
import type { Session } from "@/lib/auth";
import { RequireRole } from "@/lib/auth/RequireRole";
import { cn } from "@/lib/cn";
import { greetingFor, SEVERITY_LABEL, TRIGGER_LABEL } from "@/lib/format";
import { useNow } from "@/lib/hooks/useNow";
import { usePolling } from "@/lib/hooks/usePolling";
import { EscalationQueue, type QueueFilter, type SeverityFilter } from "./EscalationQueue";
import { RiskInfo } from "./RiskInfo";
import { PatientDrawer } from "./PatientDrawer";
import { PatientTable } from "./PatientTable";

const POLL_MS = 5000;
const HIGHLIGHT_MS = 12_000;

/** Route entry: guards the dashboard for signed-in clinicians. */
export function ClinicianDashboardRoute() {
  return <RequireRole role="clinician">{(session) => <ClinicianDashboard session={session} />}</RequireRole>;
}

export function ClinicianDashboard({ session }: { session: Session }) {
  const now = useNow();
  const [filter, setFilter] = useState<QueueFilter>("active");
  const [escalations, setEscalations] = useState<EscalationOut[] | undefined>(undefined);
  const [active, setActive] = useState<EscalationOut[] | undefined>(undefined);
  const [patients, setPatients] = useState<PatientRow[] | undefined>(undefined);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [patientsError, setPatientsError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<Set<string>>(() => new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const seenIds = useRef<Set<string> | null>(null);
  const filterRef = useRef(filter);
  const { toasts, push, dismiss } = useToasts(8000);

  const flagNew = useCallback(
    (list: EscalationOut[]) => {
      if (seenIds.current === null) {
        seenIds.current = new Set(list.map((e) => e.id));
        return;
      }
      const fresh = list.filter((e) => !seenIds.current!.has(e.id));
      fresh.forEach((e) => seenIds.current!.add(e.id));
      if (fresh.length === 0) return;
      const top = fresh[0];
      push({
        tone: top.severity === "emergency" || top.severity === "high" ? "alert" : "info",
        title: `New ${SEVERITY_LABEL[top.severity].toLowerCase()} escalation · ${top.patient_name}`,
        body: fresh.length > 1 ? `${fresh.length} new escalations in the queue.` : TRIGGER_LABEL[top.trigger_type],
      });
      setHighlight((h) => new Set([...h, ...fresh.map((e) => e.id)]));
      setTimeout(() => {
        setHighlight((h) => {
          const next = new Set(h);
          fresh.forEach((e) => next.delete(e.id));
          return next;
        });
      }, HIGHLIGHT_MS);
    },
    [push],
  );

  const refresh = useCallback(
    async (signal: AbortSignal) => {
      const currentFilter = filterRef.current;
      const [activeRes, viewRes, patientsRes] = await Promise.allSettled([
        listEscalations("active", signal),
        currentFilter === "active" ? Promise.resolve(null) : listEscalations(currentFilter, signal),
        listPatients(signal),
      ]);
      if (signal.aborted) return;

      if (activeRes.status === "fulfilled") {
        setActive(activeRes.value);
        flagNew(activeRes.value);
        setQueueError(null);
        if (currentFilter === "active") setEscalations(activeRes.value);
      } else {
        setQueueError(`Couldn't refresh the queue: ${errorMessage(activeRes.reason)}`);
      }
      if (viewRes.status === "fulfilled" && viewRes.value) setEscalations(viewRes.value);
      if (patientsRes.status === "fulfilled") {
        setPatients(patientsRes.value);
        setPatientsError(null);
      } else {
        setPatientsError(errorMessage(patientsRes.reason));
      }
      if (activeRes.status === "fulfilled") setLastUpdated(Date.now());
    },
    [flagNew],
  );

  usePolling(refresh, POLL_MS);

  function changeFilter(next: QueueFilter) {
    filterRef.current = next;
    setFilter(next);
    setEscalations(undefined);
    void refresh(new AbortController().signal);
  }

  async function onUpdate(id: string, status: EscalationStatus, notes?: string) {
    try {
      const updated = await updateEscalation(id, { status, clinician_notes: notes });
      const keep = (e: EscalationOut) =>
        filter === "all" || (filter === "active" ? e.status !== "resolved" : e.status === filter);
      setEscalations((list) =>
        (list ?? []).map((e) => (e.id === id ? updated : e)).filter((e) => e.id !== id || keep(updated)),
      );
      setActive((list) => list?.map((e) => (e.id === id ? updated : e)).filter((e) => e.status !== "resolved"));
      setPatients((rows) =>
        rows?.map((r) =>
          r.id === updated.patient_id && status === "resolved"
            ? {
                ...r,
                open_escalations: Math.max(0, r.open_escalations - 1),
                open_emergencies:
                  r.open_emergencies !== undefined && updated.severity === "emergency"
                    ? Math.max(0, r.open_emergencies - 1)
                    : r.open_emergencies,
                open_high:
                  r.open_high !== undefined && updated.severity === "high" ? Math.max(0, r.open_high - 1) : r.open_high,
              }
            : r,
        ),
      );
      push({
        tone: "success",
        title: status === "resolved" ? "Escalation resolved" : status === "acknowledged" ? "Acknowledged" : "Reopened",
        body: updated.patient_name,
      });
    } catch (err) {
      push({ tone: "alert", title: "Update failed", body: errorMessage(err) });
    }
  }

  function onDemoReset(result: DemoResetOut) {
    push({ tone: "success", title: "Demo patient reset", body: describeReset(result) });
    setSelectedId(null); // its cached chat and check-ins are gone now
    void refresh(new AbortController().signal);
  }

  function onProfileSaved(saved: PatientOut) {
    setPatients((rows) =>
      rows?.map((r) =>
        r.id === saved.id ? { ...r, procedure_name: saved.procedure_name, surgery_date: saved.surgery_date } : r,
      ),
    );
    push({ tone: "success", title: "Profile saved", body: saved.full_name });
    void refresh(new AbortController().signal);
  }

  // Real escalations a person still has to close, not model output.
  const emergencies = active?.filter((e) => e.severity === "emergency").length;
  // Model output from each patient's latest check-in.
  const modelHigh = patients?.filter((p) => p.latest_risk?.risk_level === "high").length;
  const selectedRow = patients?.find((p) => p.id === selectedId);

  // Client-side search (name or procedure) and severity filter.
  const q = query.trim().toLowerCase();
  const procedureOf = new Map((patients ?? []).map((p) => [p.id, p.procedure_name]));
  const matchesQuery = (name: string, procedure: string | undefined) =>
    q === "" || name.toLowerCase().includes(q) || Boolean(procedure?.toLowerCase().includes(q));
  const shownPatients = patients?.filter((p) => matchesQuery(p.full_name, p.procedure_name));
  const shownEscalations = escalations?.filter(
    (e) => (severity === "all" || e.severity === severity) && matchesQuery(e.patient_name, procedureOf.get(e.patient_id)),
  );
  const narrowedQueue = severity !== "all" || q !== "";

  return (
    <>
      <AppHeader user={session.user} />
      <main id="main" className="flex-1 bg-surface-soft">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-10">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="flex min-w-0 flex-col gap-1">
              <p className="text-sm font-bold text-brand-gray">{now !== null ? greetingFor(now) : "Hello"},</p>
              <h1 className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
                Dr. {session.user.full_name.replace(/^Dr\.?\s+/i, "").split(/\s+/).pop()}
              </h1>
              <p className="text-ink-soft">
                Here&rsquo;s who needs you. Foggy answers from each patient&rsquo;s plan and offers to message you
                when it can&rsquo;t; nothing is sent without the patient&rsquo;s OK.
              </p>
            </div>
            <DemoResetControl variant="button" onReset={onDemoReset} />
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat icon={<BellRing className="size-5" />} label="Active escalations" value={active?.length} tone={active?.length ? "cyan" : "plain"} />
            <Stat icon={<AlertOctagon className="size-5" />} label="Open emergencies" value={emergencies} tone={emergencies ? "red" : "plain"} />
            <Stat icon={<UsersRound className="size-5" />} label="Patients" value={patients?.length} tone="plain" />
            <Stat
              icon={<HeartPulse className="size-5" />}
              label="Risk model: high"
              hint="Model output from last check-ins"
              value={modelHigh}
              tone={modelHigh ? "amber" : "plain"}
            />
          </dl>

          <div className="mt-6 flex flex-col gap-1.5 sm:max-w-md">
            <label htmlFor="patient-search" className="text-sm font-bold text-ink-soft">
              Search patients
            </label>
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-brand-gray"
                aria-hidden="true"
              />
              <Input
                id="patient-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Name or procedure"
                autoComplete="off"
                className="pl-10"
                aria-describedby="patient-search-hint"
              />
            </div>
            <p id="patient-search-hint" className="text-xs text-brand-gray">
              Filters the queue and the patient list.
            </p>
          </div>

          {/* grid-cols-1 (minmax(0,1fr)) matters: an implicit auto column grows to the widest
              nowrap text inside it, which pushed phones out to ~750 px. */}
          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <EscalationQueue
              items={shownEscalations}
              loading={escalations === undefined}
              error={queueError}
              filter={filter}
              onFilter={changeFilter}
              severity={severity}
              onSeverity={setSeverity}
              narrowed={narrowedQueue}
              onUpdate={onUpdate}
              onOpenPatient={setSelectedId}
              highlightIds={highlight}
              now={now}
              lastUpdated={lastUpdated}
            />
            <div className="min-w-0 xl:sticky xl:top-24 xl:self-start">
              <PatientTable
                rows={shownPatients}
                active={active}
                loading={patients === undefined}
                error={patientsError}
                now={now}
                onOpen={(r) => setSelectedId(r.id)}
                emptyFiltered={Boolean(patients?.length) && q !== ""}
                riskInfo={<RiskInfo />}
              />
            </div>
          </div>
        </div>
      </main>

      <PatientDrawer
        patientId={selectedId}
        row={selectedRow}
        escalations={active ?? []}
        now={now}
        onClose={() => setSelectedId(null)}
        onProfileSaved={onProfileSaved}
      />
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
  );
}

function Stat({
  icon,
  label,
  hint,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  /** Small second line under the label (e.g. "model output"). */
  hint?: string;
  /** undefined while loading: shows a skeleton, never a flash of 0. */
  value: number | undefined;
  tone: "plain" | "cyan" | "red" | "amber";
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 items-center gap-3 rounded-[1.5rem] bg-white p-4 shadow-soft ring-1 sm:p-5",
        tone === "red" ? "ring-brand-red/30" : tone === "amber" ? "ring-sev-medium/35" : "ring-line/70",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "grid size-11 shrink-0 place-items-center rounded-2xl max-sm:hidden",
          tone === "red"
            ? "bg-brand-red/10 text-brand-red"
            : tone === "amber"
              ? "bg-sev-medium/14 text-[#7d5600]"
              : "bg-surface-pale text-brand-cyan-strong",
        )}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <dt className="text-xs leading-snug font-bold break-words text-brand-gray sm:text-sm">
          {label}
          {hint ? <span className="block text-[0.7rem] font-semibold text-brand-gray/85">{hint}</span> : null}
        </dt>
        <dd
          className={cn(
            "text-2xl font-black tabular-nums",
            tone === "red" ? "text-brand-red" : tone === "amber" ? "text-[#7d5600]" : "text-ink",
          )}
        >
          {value === undefined ? (
            <>
              <Skeleton className="mt-1 h-7 w-10" />
              <span className="sr-only">Loading</span>
            </>
          ) : (
            value
          )}
        </dd>
      </div>
    </div>
  );
}
