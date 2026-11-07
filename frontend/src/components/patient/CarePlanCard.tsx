"use client";

import { Bandage, BookHeart, Footprints, PhoneCall, Pill, Snowflake, type LucideIcon } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { SkeletonLines } from "@/components/ui/Skeleton";
import type { CarePlanOut } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";

function iconFor(section: string | null): LucideIcon {
  const s = (section ?? "").toLowerCase();
  if (s.includes("wound") || s.includes("incision")) return Bandage;
  if (s.includes("activ") || s.includes("walk") || s.includes("exercise")) return Footprints;
  if (s.includes("pain") || s.includes("swell")) return Snowflake;
  if (s.includes("medic") || s.includes("drug")) return Pill;
  if (s.includes("call") || s.includes("emergenc") || s.includes("warning")) return PhoneCall;
  return BookHeart;
}

function isUrgent(section: string | null) {
  const s = (section ?? "").toLowerCase();
  return s.includes("when to call") || s.includes("emergenc") || s.includes("warning");
}

export function CarePlanCard({
  plan,
  loading,
  error,
}: {
  plan: CarePlanOut | null | undefined;
  loading: boolean;
  error: string | null;
}) {
  return (
    <Card aria-labelledby="plan-title">
      <CardHeader
        id="plan-title"
        icon={<BookHeart className="size-5" aria-hidden="true" />}
        title="Your care plan"
        description={
          plan ? `${plan.title} · from your care team, ${formatDate(plan.created_at)}` : "Written by your care team"
        }
      />
      {loading && !plan ? <SkeletonLines lines={5} /> : null}
      {error ? (
        <p role="alert" className="text-sm font-semibold text-brand-red-dark">
          Couldn&rsquo;t load your care plan: {error}
        </p>
      ) : null}
      {!loading && !error && plan === null ? (
        <p className="rounded-2xl bg-surface-soft p-4 text-sm text-ink-soft">
          Your care team hasn&rsquo;t shared a plan yet. Foggy will answer from it as soon as they do.
        </p>
      ) : null}
      {plan ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {plan.chunks
            .slice()
            .sort((a, b) => a.chunk_index - b.chunk_index)
            .map((chunk) => {
              const Icon = iconFor(chunk.section);
              const urgent = isUrgent(chunk.section);
              return (
                <li
                  key={chunk.id}
                  className={cn(
                    "rounded-3xl p-4 sm:p-5",
                    urgent ? "bg-brand-red/6 ring-1 ring-brand-red/20 sm:col-span-2" : "bg-surface-soft ring-1 ring-line/60",
                  )}
                >
                  <h3 className="flex items-center gap-2 font-extrabold text-ink">
                    <span
                      className={cn(
                        "grid size-8 place-items-center rounded-xl",
                        urgent ? "bg-white text-brand-red" : "bg-white text-brand-cyan-strong",
                      )}
                    >
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    {chunk.section ?? "Instructions"}
                  </h3>
                  <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-soft">{chunk.content}</p>
                </li>
              );
            })}
        </ul>
      ) : null}
    </Card>
  );
}
