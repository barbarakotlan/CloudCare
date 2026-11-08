"use client";

import { ChevronRight, UsersRound } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { PENDING_SETUP_PROCEDURE, type EscalationOut, type PatientRow } from "@/lib/api/types";
import { daysSince, relativeTime } from "@/lib/format";
import { FinishSetupBadge } from "./PatientDrawer";
import { CurrentStatusChip, RiskModelSummary, sortWorklist, urgencyOf } from "./urgency";

const needsSetup = (r: PatientRow) => r.procedure_name === PENDING_SETUP_PROCEDURE;

export function PatientTable({
  rows,
  active,
  loading,
  error,
  now,
  onOpen,
  toolbar,
  emptyFiltered = false,
  riskInfo,
}: {
  rows: PatientRow[] | undefined;
  /** Active escalations, used to count open alerts when the server doesn't send counts. */
  active: EscalationOut[] | undefined;
  loading: boolean;
  error: string | null;
  now: number | null;
  onOpen: (row: PatientRow) => void;
  /** Search box and filters, rendered under the header. */
  toolbar?: ReactNode;
  /** Rows exist but the current search/filter hides all of them. */
  emptyFiltered?: boolean;
  /** Explainer shown next to the "Risk model" heading. */
  riskInfo?: ReactNode;
}) {
  const sorted = rows ? sortWorklist(rows, active) : undefined;
  return (
    <Card aria-labelledby="patients-title" className="min-w-0">
      <CardHeader
        id="patients-title"
        icon={<UsersRound className="size-5" aria-hidden="true" />}
        title="My patients"
        description="Open emergencies first, then high alerts, then model risk"
      />
      {toolbar}
      {error ? (
        <p role="alert" className="rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
          {error}
        </p>
      ) : null}
      {loading && !rows ? <Skeleton className="h-28" /> : null}
      {sorted && sorted.length === 0 ? (
        <p className="text-sm text-brand-gray">
          {emptyFiltered ? "No patients match this search." : "No patients are assigned to you yet."}
        </p>
      ) : null}

      {sorted && sorted.length > 0 ? (
        <>
          {riskInfo ? (
            <p className="mb-2 flex items-center gap-1 text-xs text-brand-gray md:hidden">
              Risk model: the model&rsquo;s estimate at the last check-in
              {riskInfo}
            </p>
          ) : null}
          {/* Mobile: cards */}
          <ul className="flex flex-col gap-2 md:hidden">
            {sorted.map((r) => (
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
                      <p className="text-sm break-words text-brand-gray">
                        {r.procedure_name}
                        {now !== null ? ` · day ${daysSince(r.surgery_date, now)}` : ""}
                      </p>
                    )}
                    <div className="mt-2 flex flex-col items-start gap-1.5">
                      <CurrentStatusChip urgency={urgencyOf(r, active)} />
                      <span className="text-[0.7rem] font-extrabold tracking-wide text-brand-gray uppercase">
                        Risk model
                      </span>
                      <RiskModelSummary row={r} now={now} className="-mt-1" />
                    </div>
                  </div>
                  <ChevronRight className="size-5 shrink-0 text-brand-gray" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>

          {/* Tablet and desktop: table (scrolls inside the card if it ever has to) */}
          <div className="-mx-2 hidden overflow-x-auto md:block">
            <table className="w-full border-separate border-spacing-y-1 text-left">
              <thead>
                <tr className="text-xs font-extrabold tracking-wide whitespace-nowrap text-brand-gray uppercase">
                  <th scope="col" className="px-2 py-2">Patient</th>
                  <th scope="col" className="px-2 py-2">Current status</th>
                  <th scope="col" className="px-2 py-2">
                    <span className="inline-flex items-center gap-1">
                      Risk model
                      {riskInfo}
                    </span>
                  </th>
                  <th scope="col" className="px-2 py-2">Last check-in</th>
                  <th scope="col" className="w-8 px-1 py-2">
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.id} className="group cursor-pointer" onClick={() => onOpen(r)}>
                    <td className="rounded-l-2xl bg-surface-soft py-3 pr-2 pl-3 align-top group-hover:bg-surface-pale">
                      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpen(r);
                          }}
                          className="rounded-md text-left font-extrabold text-ink underline-offset-4 hover:text-brand-cyan-strong hover:underline"
                        >
                          {r.full_name}
                        </button>
                        {needsSetup(r) ? <FinishSetupBadge /> : null}
                      </p>
                      {needsSetup(r) ? (
                        <p className="text-sm text-brand-gray">Add procedure and dates</p>
                      ) : (
                        <p className="line-clamp-2 max-w-[17rem] min-w-[12rem] text-sm text-brand-gray" title={r.procedure_name}>
                          {now !== null ? `Day ${daysSince(r.surgery_date, now)} · ` : ""}
                          {r.procedure_name}
                        </p>
                      )}
                    </td>
                    <td className="bg-surface-soft px-2 py-3 align-top whitespace-nowrap group-hover:bg-surface-pale">
                      <CurrentStatusChip urgency={urgencyOf(r, active)} />
                    </td>
                    <td className="bg-surface-soft px-2 py-3 align-top group-hover:bg-surface-pale">
                      <RiskModelSummary row={r} now={now} stacked />
                    </td>
                    <td className="bg-surface-soft px-2 py-3 align-top text-sm whitespace-nowrap text-ink-soft group-hover:bg-surface-pale">
                      {r.last_checkin_at ? (now !== null ? relativeTime(r.last_checkin_at, now) : "…") : "Never"}
                    </td>
                    <td className="rounded-r-2xl bg-surface-soft px-1 py-3 pr-3 align-top text-right group-hover:bg-surface-pale">
                      <ChevronRight className="mt-0.5 size-5 text-brand-gray group-hover:text-brand-cyan-strong" aria-hidden="true" />
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
