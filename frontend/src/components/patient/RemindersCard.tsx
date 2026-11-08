"use client";

import { BellRing, CalendarDays, Check, Clock3, MapPin, Pill, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import type { ToastItem } from "@/components/ui/Toast";
import { ApiError, errorMessage } from "@/lib/api/client";
import {
  asNeededMedications,
  buildDoses,
  getMyAppointments,
  getMyMedicationLogs,
  getMyMedications,
  localDayKey,
  logKey,
  logMedication,
  startOfLocalDay,
  upcomingAppointments,
  type Dose,
  type MedicationLog,
} from "@/lib/api/reminders";
import { cn } from "@/lib/cn";
import { formatClock, formatDate } from "@/lib/format";
import { useAsync } from "@/lib/hooks/useAsync";

type Notify = (toast: Omit<ToastItem, "id">) => void;
/** "pending" undoes an earlier answer. */
type Answer = "taken" | "skipped" | "pending";

const FAILURE_TITLE: Record<Answer, string> = {
  taken: "Couldn’t save that dose",
  skipped: "Couldn’t skip that dose",
  pending: "Couldn’t undo that dose",
};

/** How a dose reads to the patient right now. */
type DoseState = "scheduled" | "due" | "overdue" | "taken" | "skipped" | "missed";

const OVERDUE_AFTER_MS = 60 * 60 * 1000;

function doseState(dose: Dose, now: number | null): DoseState {
  if (dose.status === "taken" || dose.status === "skipped" || dose.status === "missed") return dose.status;
  if (now === null || dose.at > now) return "scheduled";
  return now - dose.at > OVERDUE_AFTER_MS ? "overdue" : "due";
}

const DOSE_STATE_LABEL: Record<DoseState, string> = {
  scheduled: "scheduled",
  due: "due now",
  overdue: "overdue",
  taken: "taken",
  skipped: "skipped",
  missed: "missed",
};

const DOSE_STATE_CLASS: Record<DoseState, string> = {
  scheduled: "text-brand-gray",
  due: "text-[#7d5600]",
  overdue: "text-brand-red-dark",
  taken: "text-[#146b49]",
  skipped: "text-brand-gray",
  missed: "text-brand-red-dark",
};

/** Replace any log for the same dose with `log`. */
function upsertLog(list: MedicationLog[] | undefined, log: MedicationLog): MedicationLog[] {
  const key = logKey(log.medication_id, log.scheduled_for);
  return [...(list ?? []).filter((l) => logKey(l.medication_id, l.scheduled_for) !== key), log];
}

function LoadError({ what, error, onRetry }: { what: string; error: string; onRetry: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-brand-red/6 px-4 py-3 ring-1 ring-brand-red/20">
      <p role="alert" className="text-sm font-semibold text-brand-red-dark">
        Couldn&rsquo;t load {what}: {error}
      </p>
      <Button size="sm" variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function RemindersCard({ now, notify }: { now: number | null; notify: Notify }) {
  // The patient's local day; null until the clock is known on the client.
  const dayKey = now === null ? null : localDayKey(now);

  const meds = useAsync("reminders:meds", (signal) => getMyMedications(signal));
  const logs = useAsync(dayKey === null ? null : `reminders:logs:${dayKey}`, (signal) =>
    getMyMedicationLogs(startOfLocalDay(dayKey ?? localDayKey(Date.now())), signal),
  );
  const appts = useAsync("reminders:appts", (signal) => getMyAppointments(signal));
  const [saving, setSaving] = useState<ReadonlySet<string>>(() => new Set());
  // Older servers reject "pending"; hide Undo once that happens.
  const [canUndo, setCanUndo] = useState(true);

  const doses = useMemo(
    () => (meds.data && logs.data && dayKey ? buildDoses(meds.data, logs.data, dayKey) : null),
    [meds.data, logs.data, dayKey],
  );
  const asNeeded = useMemo(
    () => (meds.data && dayKey ? asNeededMedications(meds.data, dayKey) : []),
    [meds.data, dayKey],
  );
  const upcoming = useMemo(
    () => (appts.data && now !== null ? upcomingAppointments(appts.data, now) : null),
    [appts.data, now],
  );

  const scheduleError = meds.error ?? logs.error;
  const scheduleLoading = !scheduleError && (!meds.data || (meds.data.length > 0 && !logs.data));
  const takenCount = doses?.filter((d) => d.status === "taken").length ?? 0;

  function retrySchedule() {
    if (meds.error) meds.reload();
    if (logs.error) logs.reload();
  }

  async function answer(dose: Dose, status: Answer) {
    const previous = logs.data?.find((l) => logKey(l.medication_id, l.scheduled_for) === dose.key);
    setSaving((s) => new Set(s).add(dose.key));
    // Optimistic: show the new state right away, roll back if the server says no.
    logs.setData((list) =>
      upsertLog(list, {
        id: previous?.id ?? `pending:${dose.key}`,
        medication_id: dose.medication.id,
        scheduled_for: dose.scheduled_for,
        status,
        responded_at: status === "pending" ? null : new Date().toISOString(),
      }),
    );
    try {
      const saved = await logMedication(dose.medication.id, dose.scheduled_for, status);
      logs.setData((list) => upsertLog(list, saved));
    } catch (err) {
      logs.setData((list) => {
        const rest = (list ?? []).filter((l) => logKey(l.medication_id, l.scheduled_for) !== dose.key);
        return previous ? [...rest, previous] : rest;
      });
      const unsupported =
        status === "pending" && err instanceof ApiError && [404, 405, 422].includes(err.status);
      if (unsupported) setCanUndo(false);
      notify({
        tone: "alert",
        title: FAILURE_TITLE[status],
        body: unsupported
          ? "Undo isn’t available yet. Ask your care team if you need a dose corrected."
          : errorMessage(err),
      });
    } finally {
      setSaving((s) => {
        const next = new Set(s);
        next.delete(dose.key);
        return next;
      });
    }
  }

  let description = "Medications and appointments";
  if (doses && doses.length > 0) description = `${takenCount} of ${doses.length} doses taken today`;
  else if (doses && meds.data && meds.data.length > 0) description = "No scheduled doses today";

  return (
    <Card aria-labelledby="reminders-title" aria-busy={scheduleLoading || undefined}>
      <CardHeader
        id="reminders-title"
        icon={<BellRing className="size-5" aria-hidden="true" />}
        title="Today’s reminders"
        description={description}
      />

      {scheduleLoading ? <SkeletonLines lines={3} /> : null}
      {scheduleError ? <LoadError what="your medications" error={scheduleError} onRetry={retrySchedule} /> : null}

      {!scheduleError && meds.data && meds.data.length === 0 ? (
        <p className="rounded-2xl bg-surface-soft p-4 text-sm text-ink-soft">
          No medications yet. When your care team adds them, your dose reminders will show up here.
        </p>
      ) : null}

      {!scheduleError && doses && doses.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {doses.map((dose) => {
            const state = doseState(dose, now);
            const taken = state === "taken";
            const skipped = state === "skipped";
            const answered = skipped || state === "missed";
            const due = state === "due" || state === "overdue";
            const busy = saving.has(dose.key);
            const label = `${dose.medication.name} ${formatClock(dose.time)}`;
            return (
              <li
                key={dose.key}
                className={cn(
                  "flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl px-3 py-2.5 ring-1 transition-colors sm:flex-nowrap sm:px-4",
                  taken
                    ? "bg-ok/6 ring-ok/20"
                    : answered
                      ? "bg-surface-soft ring-line/50"
                      : state === "overdue"
                        ? "bg-brand-red/5 ring-brand-red/20"
                        : state === "due"
                          ? "bg-sev-medium/8 ring-sev-medium/25"
                          : "bg-white ring-line",
                )}
              >
                <span
                  className={cn(
                    "grid size-10 shrink-0 place-items-center rounded-xl",
                    taken
                      ? "bg-ok/15 text-[#146b49]"
                      : answered
                        ? "bg-white text-brand-gray"
                        : "bg-surface-pale text-brand-cyan-strong",
                  )}
                >
                  {taken ? (
                    <Check className="size-5" strokeWidth={3} aria-hidden="true" />
                  ) : (
                    <Pill className="size-5" aria-hidden="true" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p
                    className={cn("truncate font-bold", taken || answered ? "text-ink-soft" : "text-ink")}
                    title={`${dose.medication.name} ${dose.medication.dosage}`}
                  >
                    {dose.medication.name}{" "}
                    <span className={cn("font-semibold", taken || answered ? "text-brand-gray" : "text-ink-soft")}>
                      {dose.medication.dosage}
                    </span>
                  </p>
                  <p className="flex items-center gap-1 text-xs whitespace-nowrap text-brand-gray">
                    <Clock3 className="size-3.5" aria-hidden="true" />
                    {formatClock(dose.time)}
                    <span className={cn("font-bold", DOSE_STATE_CLASS[state], taken && "sm:hidden")}>
                      {" "}
                      · {DOSE_STATE_LABEL[state]}
                    </span>
                  </p>
                </div>
                {taken ? (
                  <div className="flex shrink-0 items-center gap-1">
                    {/* Phones: the check and "· taken" carry it, leaving room for the medicine name. */}
                    <Badge tone="green" className="max-sm:hidden">
                      Taken
                    </Badge>
                    {canUndo ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="px-2.5 sm:px-3"
                        disabled={busy}
                        onClick={() => void answer(dose, "pending")}
                        aria-label={`Undo: ${label} not taken yet`}
                      >
                        <Undo2 className="size-4" aria-hidden="true" />
                        Undo
                      </Button>
                    ) : null}
                  </div>
                ) : (
                  <div
                    className={cn(
                      "flex shrink-0 items-center justify-end gap-1",
                      // Two buttons don't fit beside the name on phones: give them their own row.
                      (due || (skipped && canUndo)) && "w-full sm:w-auto",
                    )}
                  >
                    {skipped && canUndo ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="px-3"
                        disabled={busy}
                        onClick={() => void answer(dose, "pending")}
                        aria-label={`Undo skipping ${label}`}
                      >
                        <Undo2 className="size-4" aria-hidden="true" />
                        Undo
                      </Button>
                    ) : null}
                    {due ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="px-3"
                        disabled={busy}
                        onClick={() => void answer(dose, "skipped")}
                        aria-label={`Skip ${label}`}
                      >
                        Skip
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant={due ? "primary" : "soft"}
                      disabled={busy}
                      onClick={() => void answer(dose, "taken")}
                      aria-label={`Mark ${label} as taken`}
                    >
                      Mark taken
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      {!scheduleError && asNeeded.length > 0 ? (
        <div className="mt-3 rounded-2xl bg-surface-soft px-4 py-3 text-sm text-ink-soft">
          <span className="font-bold text-ink">As needed: </span>
          {asNeeded.map((m) => `${m.name} ${m.dosage}${m.instructions ? `, ${m.instructions.toLowerCase()}` : ""}`).join(" · ")}
        </div>
      ) : null}

      <h3 className="mt-6 mb-2 text-sm font-extrabold tracking-wide text-brand-gray uppercase">Coming up</h3>
      {appts.error ? (
        <LoadError what="your appointments" error={appts.error} onRetry={appts.reload} />
      ) : !upcoming ? (
        <SkeletonLines lines={2} />
      ) : upcoming.length === 0 ? (
        <p className="rounded-2xl bg-surface-soft p-4 text-sm text-ink-soft">No upcoming appointments.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {upcoming.map((a) => (
            <li key={a.id} className="flex gap-3 rounded-2xl bg-white p-3.5 ring-1 ring-line">
              <span className="flex size-12 shrink-0 flex-col items-center justify-center rounded-xl bg-surface-pale leading-none text-brand-cyan-strong">
                <span className="text-[0.65rem] font-extrabold uppercase">{formatDate(a.scheduled_at, { month: "short" })}</span>
                <span className="text-lg font-black">{formatDate(a.scheduled_at, { day: "numeric" })}</span>
              </span>
              <div className="min-w-0 text-sm">
                <p className="font-bold text-ink">{a.title}</p>
                <p className="flex items-center gap-1 text-brand-gray">
                  <CalendarDays className="size-3.5 shrink-0" aria-hidden="true" />
                  {formatDate(a.scheduled_at, { weekday: "short", hour: "numeric", minute: "2-digit" })}
                  {a.provider_name ? ` · ${a.provider_name}` : ""}
                </p>
                {a.location ? (
                  <p className="flex items-center gap-1 truncate text-brand-gray">
                    <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                    {a.location}
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
