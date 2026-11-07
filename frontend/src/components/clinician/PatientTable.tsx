"use client";

import { ChevronRight, UsersRound } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { PENDING_SETUP_PROCEDURE, type PatientRow } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { daysSince, relativeTime, RISK_LABEL } from "@/lib/format";
import { FinishSetupBadge } from "./PatientDrawer";
import { RISK_TONE } from "./severity";

const needsSetup = (r: PatientRow) => r.procedure_name === PENDING_SETUP_PROCEDURE;

function RiskCell({ row }: { row: PatientRow }) {
  if (!row.latest_risk) return <Badge tone="gray">No check-ins</Badge>;
  return (
    <span className="inline-flex items-center gap-2">
      <Badge tone={RISK_TONE[row.latest_risk.risk_level]} dot>
        {RISK_LABEL[row.latest_risk.risk_level]}
      </Badge>
      <span className="text-xs font-bold text-brand-gray tabular-nums">{Math.round(row.latest_risk.score * 100)}%</span>
    </span>
  );
}

function OpenCount({ n }: { n: number }) {
  return (
    <span
      className={cn(
        "inline-grid h-7 min-w-7 place-items-center rounded-full px-2 text-sm font-extrabold tabular-nums",
        n > 0 ? "bg-brand-red text-white" : "bg-surface-pale text-brand-gray",
      )}
    >
      <span className="sr-only">{n} open escalations</span>
      <span aria-hidden="true">{n}</span>
    </span>
  );
}

export function PatientTable({
  rows,
  loading,
  error,
  now,
  onOpen,
}: {
  rows: PatientRow[] | undefined;
  loading: boolean;
  error: string | null;
  now: number | null;
  onOpen: (row: PatientRow) => void;
}) {
  return (
    <Card aria-labelledby="patients-title">
      <CardHeader
        id="patients-title"
        icon={<UsersRound className="size-5" aria-hidden="true" />}
        title="My patients"
        description="Highest recovery risk first"
      />
      {error ? (
        <p role="alert" className="rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
          {error}
        </p>
      ) : null}
      {loading && !rows ? <Skeleton className="h-28" /> : null}
      {rows && rows.length === 0 ? <p className="text-sm text-brand-gray">No patients are assigned to you yet.</p> : null}

      {rows && rows.length > 0 ? (
        <>
          {/* Mobile: cards */}
          <ul className="flex flex-col gap-2 md:hidden">
            {rows.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => onOpen(r)}
                  className="flex w-full items-center gap-3 rounded-2xl bg-surface-soft p-4 text-left ring-1 ring-line/60 transition-colors hover:bg-surface-pale"
                >
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-extrabold text-ink">
                      <span className="min-w-0 break-words">{r.full_name}</span>
                      {needsSetup(r) ? <FinishSetupBadge /> : null}
                    </p>
                    {needsSetup(r) ? null : (
                      <p className="truncate text-sm text-brand-gray">
                        {r.procedure_name}
                        {now !== null ? ` · day ${daysSince(r.surgery_date, now)}` : ""}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <RiskCell row={r} />
                    </div>
                  </div>
                  <OpenCount n={r.open_escalations} />
                  <ChevronRight className="size-5 text-brand-gray" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>

          {/* Desktop: table */}
          <div className="-mx-2 hidden overflow-x-auto md:block">
            <table className="w-full border-separate border-spacing-y-1 text-left">
              <thead>
                <tr className="text-xs font-extrabold tracking-wide whitespace-nowrap text-brand-gray uppercase">
                  <th scope="col" className="px-3 py-2">Patient</th>
                  <th scope="col" className="px-3 py-2">Latest risk</th>
                  <th scope="col" className="px-3 py-2 text-center">Open</th>
                  <th scope="col" className="px-3 py-2">Last check-in</th>
                  <th scope="col" className="px-3 py-2">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="group">
                    <td className="rounded-l-2xl bg-surface-soft px-3 py-3 group-hover:bg-surface-pale">
                      <p className="flex items-center gap-2 font-extrabold whitespace-nowrap text-ink">
                        {r.full_name}
                        {needsSetup(r) ? <FinishSetupBadge /> : null}
                      </p>
                      {needsSetup(r) ? (
                        <p className="text-sm text-brand-gray">Add procedure and dates</p>
                      ) : (
                        <p className="max-w-[13rem] truncate text-sm text-brand-gray" title={r.procedure_name}>
                          {now !== null ? `Day ${daysSince(r.surgery_date, now)} · ` : ""}
                          {r.procedure_name}
                        </p>
                      )}
                    </td>
                    <td className="bg-surface-soft px-3 py-3 whitespace-nowrap group-hover:bg-surface-pale">
                      <RiskCell row={r} />
                    </td>
                    <td className="bg-surface-soft px-3 py-3 text-center group-hover:bg-surface-pale">
                      <OpenCount n={r.open_escalations} />
                    </td>
                    <td className="bg-surface-soft px-3 py-3 text-sm whitespace-nowrap text-ink-soft group-hover:bg-surface-pale">
                      {r.last_checkin_at ? (now !== null ? relativeTime(r.last_checkin_at, now) : "…") : "Never"}
                    </td>
                    <td className="rounded-r-2xl bg-surface-soft px-3 py-3 text-right group-hover:bg-surface-pale">
                      <button
                        type="button"
                        onClick={() => onOpen(r)}
                        className="inline-flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-sm font-bold whitespace-nowrap text-brand-cyan-strong ring-1 ring-line transition-colors hover:ring-brand-cyan"
                      >
                        Open <span className="sr-only">{r.full_name}</span>
                        <ChevronRight className="size-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </Card>
  );
}
