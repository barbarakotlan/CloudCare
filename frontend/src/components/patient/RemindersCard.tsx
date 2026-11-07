"use client";

import { BellRing, CalendarDays, Check, Clock3, MapPin, Pill } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { getMyAppointments, getMyMedications, getTodaysDoses, logMedication, type Dose } from "@/lib/api/reminders";
import { cn } from "@/lib/cn";
import { formatClock, formatDate } from "@/lib/format";
import { useAsync } from "@/lib/hooks/useAsync";

function doseKey(d: Dose) {
  return `${d.medication.id}@${d.scheduled_for}`;
}

export function RemindersCard({ surgeryDate, now }: { surgeryDate?: string; now: number | null }) {
  const doses = useAsync("doses", () => getTodaysDoses());
  const meds = useAsync("meds", () => getMyMedications());
  const appts = useAsync(`appts:${surgeryDate ?? ""}`, () => getMyAppointments(surgeryDate));
  const [saving, setSaving] = useState<string | null>(null);

  const asNeeded = (meds.data ?? []).filter((m) => m.times_of_day.length === 0);
  const takenCount = (doses.data ?? []).filter((d) => d.status === "taken").length;

  async function markTaken(dose: Dose) {
    const key = doseKey(dose);
    setSaving(key);
    try {
      await logMedication(dose.medication.id, dose.scheduled_for, "taken");
      doses.setData((list) => (list ?? []).map((d) => (doseKey(d) === key ? { ...d, status: "taken" } : d)));
    } finally {
      setSaving(null);
    }
  }

  return (
    <Card aria-labelledby="reminders-title">
      <CardHeader
        id="reminders-title"
        icon={<BellRing className="size-5" aria-hidden="true" />}
        title="Today’s reminders"
        description={doses.data ? `${takenCount} of ${doses.data.length} doses taken` : "Medications and appointments"}
        action={
          <Badge tone="gray" className="max-sm:hidden">
            Sample schedule
          </Badge>
        }
      />

      {doses.loading ? <SkeletonLines lines={3} /> : null}
      {doses.data ? (
        <ul className="flex flex-col gap-2">
          {doses.data.map((dose) => {
            const key = doseKey(dose);
            const taken = dose.status === "taken";
            const due = !taken && now !== null && new Date(dose.scheduled_for).getTime() <= now;
            return (
              <li
                key={key}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-3 py-2.5 ring-1 transition-colors sm:px-4",
                  taken ? "bg-surface-soft ring-line/50" : due ? "bg-sev-medium/8 ring-sev-medium/25" : "bg-white ring-line",
                )}
              >
                <span
                  className={cn(
                    "grid size-10 shrink-0 place-items-center rounded-xl",
                    taken ? "bg-ok/12 text-ok" : "bg-surface-pale text-brand-cyan-strong",
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
                  </p>
                </div>
                {taken ? (
                  <Badge tone="green">Taken</Badge>
                ) : (
                  <Button
                    size="sm"
                    variant={due ? "primary" : "soft"}
                    disabled={saving === key}
                    onClick={() => void markTaken(dose)}
                    aria-label={`Mark ${dose.medication.name} ${formatClock(dose.time)} as taken`}
                  >
                    Mark taken
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}

      {asNeeded.length > 0 ? (
        <div className="mt-3 rounded-2xl bg-surface-soft px-4 py-3 text-sm text-ink-soft">
          <span className="font-bold text-ink">As needed: </span>
          {asNeeded.map((m) => `${m.name} ${m.dosage}${m.instructions ? `, ${m.instructions.toLowerCase()}` : ""}`).join(" · ")}
        </div>
      ) : null}

      <h3 className="mt-6 mb-2 text-sm font-extrabold tracking-wide text-brand-gray uppercase">Coming up</h3>
      {appts.loading ? <SkeletonLines lines={2} /> : null}
      {appts.data ? (
        <ul className="grid gap-2 sm:grid-cols-2">
          {appts.data.map((a) => (
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
      ) : null}
    </Card>
  );
}
