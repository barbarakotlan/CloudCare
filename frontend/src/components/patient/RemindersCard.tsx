"use client";

import { BellRing, CalendarDays, Check, Clock3, MapPin, Pill } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import type { ToastItem } from "@/components/ui/Toast";
import { errorMessage } from "@/lib/api/client";
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
type Answer = "taken" | "skipped";

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
        responded_at: new Date().toISOString(),
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
      notify({
        tone: "alert",
        title: status === "taken" ? "Couldn’t save that dose" : "Couldn’t skip that dose",
        body: errorMessage(err),
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
            const taken = dose.status === "taken";
            const answered = dose.status === "skipped" || dose.status === "missed";
            const due = dose.status === "pending" && now !== null && dose.at <= now;
            const busy = saving.has(dose.key);
            const label = `${dose.medication.name} ${formatClock(dose.time)}`;
            return (
              <li
                key={dose.key}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-3 py-2.5 ring-1 transition-colors sm:px-4",
                  taken || answered
                    ? "bg-surface-soft ring-line/50"
                    : due
                      ? "bg-sev-medium/8 ring-sev-medium/25"
                      : "bg-white ring-line",
                )}
              >
                <span
                  className={cn(
                    "grid size-10 shrink-0 place-items-center rounded-xl",
                    taken ? "bg-ok/12 text-ok" : answered ? "bg-white text-brand-gray" : "bg-surface-pale text-brand-cyan-strong",
                  )}
                >
                  {taken ? <Check className="size-5" aria-hidden="true" /> : <Pill className="size-5" aria-hidden="true" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn("font-bold text-ink", taken && "text-brand-gray line-through decoration-2")}>
                    {dose.medication.name} <span className="font-semibold text-ink-soft">{dose.medication.dosage}</span>
                  </p>
                  <p className="flex items-center gap-1 text-xs text-brand-gray">
                    <Clock3 className="size-3.5" aria-hidden="true" />
                    {formatClock(dose.time)}
                    {due ? <span className="font-bold text-[#7d5600]"> · due now</span> : null}
                    {answered ? <span className="font-semibold"> · {dose.status}</span> : null}
                  </p>
                </div>
                {taken ? (
                  <Badge tone="green">Taken</Badge>
                ) : (
                  <div className="flex shrink-0 items-center gap-1">
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
