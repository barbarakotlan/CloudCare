"use client";

import { AudioLines, CalendarCheck2, ClipboardCheck, Hospital } from "lucide-react";
import { CloudShape } from "@/components/brand/CloudShape";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import type { PatientOut } from "@/lib/api/types";
import { daysSince, firstName, formatDate, greetingFor } from "@/lib/format";

const RECOVERY_DAYS = 42; // typical 6-week early recovery window

export function GreetingBanner({
  profile,
  fallbackName,
  now,
  error,
  onTalk,
}: {
  profile: PatientOut | undefined;
  fallbackName: string;
  now: number | null;
  error: string | null;
  onTalk: () => void;
}) {
  const day = profile && now !== null ? daysSince(profile.surgery_date, now) : null;
  const progress = day === null ? 0 : Math.min(100, Math.round((day / RECOVERY_DAYS) * 100));
  const name = firstName(profile?.full_name ?? fallbackName);

  return (
    <section
      aria-labelledby="greeting-title"
      className="relative isolate overflow-hidden rounded-[2rem] bg-white p-6 shadow-soft ring-1 ring-line/70 sm:p-8"
    >
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[radial-gradient(90%_120%_at_100%_0%,var(--surface-pale)_0%,transparent_60%)]"
      />
      <CloudShape className="absolute -top-4 right-6 -z-10 hidden w-48 opacity-80 sm:block" fill="#ffffff" />

      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-bold text-brand-gray">{now !== null ? greetingFor(now) : "Hello"},</p>
          <h1 id="greeting-title" className="mt-0.5 text-3xl font-black tracking-tight text-ink sm:text-4xl">
            {name}
          </h1>
          {error ? (
            <p role="alert" className="mt-2 text-sm font-semibold text-brand-red-dark">
              Couldn&rsquo;t load your profile: {error}
            </p>
          ) : profile ? (
            <p className="mt-2 flex items-center gap-2 text-ink-soft">
              <Hospital className="size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
              {profile.procedure_name}
            </p>
          ) : (
            <Skeleton className="mt-3 h-5 w-64" />
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <a href="#check-in" className={buttonClasses("primary", "md")}>
            <ClipboardCheck className="size-5" aria-hidden="true" />
            Check in now
          </a>
          <Button variant="secondary" onClick={onTalk} aria-haspopup="dialog">
            <AudioLines className="size-5" aria-hidden="true" />
            Talk to Foggy
          </Button>
        </div>
      </div>

      <div className="mt-7 grid gap-4 sm:grid-cols-[auto_1fr] sm:items-center sm:gap-8">
        <div className="flex items-baseline gap-2">
          {day === null && !error ? (
            <Skeleton className="h-12 w-12" />
          ) : (
            <span className="text-5xl leading-none font-black text-brand-cyan">{day ?? "–"}</span>
          )}
          <span className="font-bold text-ink-soft">
            {day === 1 ? "day" : "days"} since surgery
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex justify-between text-xs font-bold text-brand-gray">
            <span>Surgery{profile ? ` · ${formatDate(profile.surgery_date)}` : ""}</span>
            <span>6-week check-in</span>
          </div>
          <div
            role="progressbar"
            aria-label="Recovery progress toward 6 weeks"
            aria-valuemin={0}
            aria-valuemax={RECOVERY_DAYS}
            aria-valuenow={day ?? 0}
            className="mt-2 h-3 overflow-hidden rounded-full bg-surface-pale"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-cyan to-[#4fc0de] transition-[width] duration-700"
              style={{ width: `${Math.max(progress, 3)}%` }}
            />
          </div>
          {profile ? (
            <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-brand-gray">
              {profile.discharge_date ? (
                <span className="inline-flex items-center gap-1">
                  <CalendarCheck2 className="size-3.5" aria-hidden="true" />
                  Home since {formatDate(profile.discharge_date)}
                </span>
              ) : null}
              {profile.comorbidities.length > 0 ? (
                <span>Health notes: {profile.comorbidities.join(", ")}</span>
              ) : null}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
