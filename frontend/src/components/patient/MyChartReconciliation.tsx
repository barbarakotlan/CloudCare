"use client";

import { CircleCheck, ClipboardList, TriangleAlert, type LucideIcon } from "lucide-react";
import { useMemo } from "react";
import { SkeletonLines } from "@/components/ui/Skeleton";
import type { EpicMedication } from "@/lib/api/epic";
import { getMyMedications, type Medication } from "@/lib/api/reminders";
import { cn } from "@/lib/cn";
import { useAsync } from "@/lib/hooks/useAsync";

/** MyChart prescriptions that are no longer being taken; not worth flagging. */
const INACTIVE = new Set(["stopped", "cancelled", "completed", "entered-in-error", "revoked"]);

/** Lower-case words of 3+ letters: "Acetaminophen 325 MG tablet" -> [acetaminophen, tablet]. */
function words(name: string): string[] {
  return name.toLowerCase().match(/[a-z]{3,}/g) ?? [];
}

/**
 * Same medicine when the first word of either name (normally the generic name)
 * appears in the other: "acetaminophen 325 MG oral tablet" matches "Acetaminophen".
 */
function sameMedicine(a: string, b: string): boolean {
  const wa = words(a);
  const wb = words(b);
  if (wa.length === 0 || wb.length === 0) return false;
  return wb.includes(wa[0]) || wa.includes(wb[0]);
}

type Comparison = {
  both: { epic: string; plan: string }[];
  epicOnly: string[];
  planOnly: string[];
};

function compare(epicMeds: EpicMedication[], planMeds: Medication[]): Comparison {
  const epic = epicMeds.filter((m) => !INACTIVE.has((m.status ?? "").toLowerCase()));
  const plan = planMeds.filter((m) => m.is_active);
  const both: Comparison["both"] = [];
  const epicOnly: string[] = [];
  for (const m of epic) {
    const match = plan.find((p) => sameMedicine(m.name, p.name));
    if (match) both.push({ epic: m.name, plan: `${match.name} ${match.dosage}`.trim() });
    else epicOnly.push(m.name);
  }
  const planOnly = plan
    .filter((p) => !epic.some((m) => sameMedicine(m.name, p.name)))
    .map((p) => `${p.name} ${p.dosage}`.trim());
  return { both, epicOnly, planOnly };
}

function Group({
  icon: Icon,
  tone,
  title,
  items,
}: {
  icon: LucideIcon;
  tone: "ok" | "warn" | "info";
  title: string;
  items: string[];
}) {
  if (items.length === 0) return null;
  return (
    <div
      className={cn(
        "rounded-2xl p-3 ring-1",
        tone === "ok" && "bg-ok/6 ring-ok/20",
        tone === "warn" && "bg-sev-medium/10 ring-sev-medium/30",
        tone === "info" && "bg-white ring-line",
      )}
    >
      <p className="flex items-start gap-2 text-sm font-bold text-ink">
        <Icon
          className={cn(
            "mt-0.5 size-4 shrink-0",
            tone === "ok" && "text-ok",
            tone === "warn" && "text-[#7d5600]",
            tone === "info" && "text-brand-cyan-strong",
          )}
          aria-hidden="true"
        />
        <span>
          {title} <span className="font-semibold text-brand-gray">({items.length})</span>
        </span>
      </p>
      <ul className="mt-1.5 flex flex-col gap-1 pl-6 text-sm text-ink-soft">
        {items.map((item, i) => (
          <li key={i} className="break-words">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Read-only check of MyChart prescriptions against the medications in the care
 * plan, so the patient can spot anything to ask their care team about.
 */
export function MyChartReconciliation({ epicMedications }: { epicMedications: EpicMedication[] }) {
  const planMeds = useAsync("mychart:plan-meds", (signal) => getMyMedications(signal));
  const result = useMemo(
    () => (planMeds.data ? compare(epicMedications, planMeds.data) : null),
    [epicMedications, planMeds.data],
  );

  let body;
  if (planMeds.error) {
    body = <p className="text-sm text-brand-gray">Couldn&rsquo;t load your care-plan medications to compare.</p>;
  } else if (!result) {
    body = <SkeletonLines lines={2} />;
  } else if (result.both.length + result.epicOnly.length + result.planOnly.length === 0) {
    body = <p className="text-sm text-brand-gray">No current medications in MyChart or your care plan.</p>;
  } else {
    body = (
      <div className="flex flex-col gap-2">
        <Group
          icon={CircleCheck}
          tone="ok"
          title="In both"
          items={result.both.map((b) => `${b.plan} (MyChart: ${b.epic})`)}
        />
        <Group
          icon={TriangleAlert}
          tone="warn"
          title="In MyChart, not in your care plan — ask your care team before taking"
          items={result.epicOnly}
        />
        <Group icon={ClipboardList} tone="info" title="In your care plan, not in MyChart" items={result.planOnly} />
      </div>
    );
  }

  return (
    <section aria-labelledby="mychart-compare-title" className="mb-5 rounded-3xl bg-surface-soft p-4 ring-1 ring-line/60">
      <h3 id="mychart-compare-title" className="font-extrabold text-ink">
        Medications in MyChart vs your care plan
      </h3>
      <p className="mt-0.5 mb-3 text-sm text-brand-gray">
        Matched by medicine name. Your care plan is what your care team wants you to take now.
      </p>
      {body}
    </section>
  );
}
