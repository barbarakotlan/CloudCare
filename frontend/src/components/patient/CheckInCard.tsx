"use client";

import { ClipboardCheck, LoaderCircle, PhoneCall, RotateCcw, ShieldCheck, TriangleAlert } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Input";
import { errorMessage } from "@/lib/api/client";
import { getSymptoms, logSymptoms } from "@/lib/api/symptoms";
import type { RiskLevel, SymptomIn, SymptomResult } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { factorLabel, MOBILITY_LABEL, relativeTime, RISK_LABEL } from "@/lib/format";
import { useAsync } from "@/lib/hooks/useAsync";

type Flags = Pick<SymptomIn, "wound_redness" | "wound_drainage" | "swelling" | "nausea" | "shortness_of_breath">;

const FLAG_OPTIONS: Array<{ key: keyof Flags; label: string }> = [
  { key: "swelling", label: "More swelling" },
  { key: "wound_redness", label: "Redness at incision" },
  { key: "wound_drainage", label: "Drainage from incision" },
  { key: "nausea", label: "Nausea" },
  { key: "shortness_of_breath", label: "Shortness of breath" },
];

const EMPTY_FLAGS: Flags = {
  wound_redness: false,
  wound_drainage: false,
  swelling: false,
  nausea: false,
  shortness_of_breath: false,
};

function painWord(p: number) {
  if (p === 0) return "No pain";
  if (p <= 3) return "Mild";
  if (p <= 6) return "Moderate";
  if (p <= 8) return "Severe";
  return "Worst imaginable";
}

const RISK_TONE: Record<RiskLevel, BadgeTone> = { low: "green", medium: "amber", high: "red" };

export function CheckInCard({ now }: { now: number | null }) {
  const [pain, setPain] = useState(3);
  const [temp, setTemp] = useState("");
  const [flags, setFlags] = useState<Flags>(EMPTY_FLAGS);
  const [mobility, setMobility] = useState(3);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SymptomResult | null>(null);
  const history = useAsync("symptoms", (signal) => getSymptoms(undefined, signal));
  const ids = useId();

  const tempNum = temp.trim() === "" ? null : Number(temp);
  const tempInvalid = tempNum !== null && (!Number.isFinite(tempNum) || tempNum < 90 || tempNum > 110);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (tempInvalid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await logSymptoms({
        pain_level: pain,
        temperature_f: tempNum,
        ...flags,
        mobility_level: mobility,
        free_text: notes.trim() || null,
        source: "checkin",
      });
      setResult(res);
      history.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setResult(null);
    setPain(3);
    setTemp("");
    setFlags(EMPTY_FLAGS);
    setMobility(3);
    setNotes("");
  }

  const last = history.data?.[0];

  return (
    <Card id="check-in" aria-labelledby="checkin-title" className="scroll-mt-24">
      <CardHeader
        id="checkin-title"
        icon={<ClipboardCheck className="size-5" aria-hidden="true" />}
        title="How are you feeling?"
        description={
          last && now !== null
            ? `Last check-in ${relativeTime(last.logged_at, now)} · takes about a minute`
            : "Takes about a minute. Saved to your record, where your care team can see it."
        }
      />

      {result ? (
        <CheckInResult result={result} onReset={reset} shortnessOfBreath={flags.shortness_of_breath} />
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-6" noValidate>
          {/* Pain */}
          <div>
            <div className="flex items-end justify-between gap-3">
              <label htmlFor={`${ids}-pain`} className="text-sm font-bold text-ink-soft">
                Pain right now
              </label>
              <p aria-hidden="true" className="text-right leading-none">
                <span
                  className={cn(
                    "text-3xl font-black",
                    pain >= 7 ? "text-brand-red" : pain >= 4 ? "text-sev-medium" : "text-brand-cyan",
                  )}
                >
                  {pain}
                </span>
                <span className="text-sm font-bold text-brand-gray">/10 · {painWord(pain)}</span>
              </p>
            </div>
            <input
              id={`${ids}-pain`}
              type="range"
              min={0}
              max={10}
              step={1}
              value={pain}
              onChange={(e) => setPain(Number(e.target.value))}
              aria-valuetext={`${pain} out of 10, ${painWord(pain)}`}
              className="cc-range mt-3 h-2 w-full cursor-pointer"
            />
            <div aria-hidden="true" className="mt-1 flex justify-between text-[0.7rem] font-bold text-brand-gray">
              <span>0</span>
              <span>5</span>
              <span>10</span>
            </div>
          </div>

          {/* Symptoms */}
          <fieldset>
            <legend className="text-sm font-bold text-ink-soft">Anything new since last time?</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {FLAG_OPTIONS.map((opt) => (
                <label key={opt.key} className="cursor-pointer">
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={flags[opt.key]}
                    onChange={(e) => setFlags((f) => ({ ...f, [opt.key]: e.target.checked }))}
                  />
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-bold ring-1 transition-colors select-none",
                      "bg-white text-ink-soft ring-line hover:ring-brand-cyan",
                      "peer-checked:bg-brand-cyan peer-checked:text-white peer-checked:ring-brand-cyan",
                      "peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-cyan",
                      opt.key === "shortness_of_breath" &&
                        "peer-checked:bg-brand-red peer-checked:ring-brand-red",
                    )}
                  >
                    {opt.label}
                  </span>
                </label>
              ))}
            </div>
            {flags.shortness_of_breath ? (
              <p role="alert" className="mt-3 flex items-start gap-2 rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
                <PhoneCall className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                If you&rsquo;re struggling to breathe or have chest pain, call 911 now. Don&rsquo;t wait for a reply.
              </p>
            ) : null}
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Temperature (°F, optional)"
              htmlFor={`${ids}-temp`}
              hint={tempInvalid ? undefined : "Skip if you haven’t taken it."}
            >
              <Input
                id={`${ids}-temp`}
                type="number"
                inputMode="decimal"
                step="0.1"
                min={90}
                max={110}
                placeholder="98.6"
                value={temp}
                onChange={(e) => setTemp(e.target.value)}
                aria-invalid={tempInvalid || undefined}
                aria-describedby={tempInvalid ? `${ids}-temp-err` : undefined}
              />
            </Field>
            <Field label="Getting around" htmlFor={`${ids}-mobility`}>
              <select
                id={`${ids}-mobility`}
                value={mobility}
                onChange={(e) => setMobility(Number(e.target.value))}
                className="h-12 w-full appearance-none rounded-2xl border border-line bg-white bg-[length:16px] bg-[right_1rem_center] bg-no-repeat px-4 pr-10 text-[0.98rem] text-ink focus:border-brand-cyan focus:outline-none"
                style={{
                  backgroundImage:
                    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23636363' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
                }}
              >
                {MOBILITY_LABEL.map((label, i) => (
                  <option key={label} value={i}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          {tempInvalid ? (
            <p id={`${ids}-temp-err`} role="alert" className="-mt-3 text-sm font-semibold text-brand-red-dark">
              Enter a temperature between 90 and 110 °F.
            </p>
          ) : null}

          <Field label="Anything else? (optional)" htmlFor={`${ids}-notes`}>
            <Textarea
              id={`${ids}-notes`}
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Knee feels warm after physio"
            />
          </Field>

          {error ? (
            <p role="alert" className="flex items-start gap-2 rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {error}
            </p>
          ) : null}

          <Button type="submit" size="lg" disabled={submitting || tempInvalid} className="w-full sm:w-auto sm:self-start">
            {submitting ? <LoaderCircle className="size-5 animate-spin" aria-hidden="true" /> : null}
            {submitting ? "Sending…" : "Send check-in"}
          </Button>
        </form>
      )}
    </Card>
  );
}

function CheckInResult({
  result,
  onReset,
  shortnessOfBreath,
}: {
  result: SymptomResult;
  onReset: () => void;
  shortnessOfBreath: boolean;
}) {
  const { risk, escalated } = result;
  const pct = Math.round(risk.score * 100);
  return (
    <div role="status" aria-live="polite" className="flex animate-bubble-in flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={RISK_TONE[risk.risk_level]} dot className="px-3 py-1 text-sm">
          {RISK_LABEL[risk.risk_level]}
        </Badge>
        <span className="text-sm text-brand-gray">Recovery risk score {pct}%</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-surface-pale" aria-hidden="true">
        <div
          className={cn(
            "h-full rounded-full",
            risk.risk_level === "high" ? "bg-brand-red" : risk.risk_level === "medium" ? "bg-sev-medium" : "bg-ok",
          )}
          style={{ width: `${Math.max(pct, 4)}%` }}
        />
      </div>
      {risk.top_factors.length > 0 ? (
        <p className="text-sm text-ink-soft">
          <span className="font-bold text-ink">What stood out: </span>
          {risk.top_factors.map((f) => factorLabel(f.feature)).join(", ")}
        </p>
      ) : null}

      {escalated ? (
        <div className="rounded-3xl bg-brand-red/8 p-4 ring-1 ring-brand-red/25">
          <p className="flex items-center gap-2 font-extrabold text-brand-red-dark">
            <TriangleAlert className="size-5" aria-hidden="true" />
            Your care team&rsquo;s queue has this check-in
          </p>
          <p className="mt-1 text-sm text-ink-soft">
            If you need help now, call your medical team.
            {shortnessOfBreath ? " If you have trouble breathing or chest pain, call 911 now." : ""}
          </p>
        </div>
      ) : (
        <div className="rounded-3xl bg-ok/8 p-4 ring-1 ring-ok/25">
          <p className="flex items-center gap-2 font-extrabold text-[#146b49]">
            <ShieldCheck className="size-5" aria-hidden="true" />
            No alert needed
          </p>
          <p className="mt-1 text-sm text-ink-soft">
            Thanks for checking in. Keep following your plan, and check in again tonight or whenever something changes.
          </p>
        </div>
      )}

      <Button variant="secondary" onClick={onReset} className="self-start">
        <RotateCcw className="size-4" aria-hidden="true" />
        Log another check-in
      </Button>
    </div>
  );
}
