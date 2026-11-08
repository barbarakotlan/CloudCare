"use client";

import { LoaderCircle, RotateCcw } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError, errorMessage } from "@/lib/api/client";
import { DEMO_RESET_LABEL, demoResetAvailable, resetDemoPatient, type DemoResetOut } from "@/lib/api/demo";
import { cn } from "@/lib/cn";
import { useAsync } from "@/lib/hooks/useAsync";

type Phase = { kind: "idle" } | { kind: "confirm" } | { kind: "busy" } | { kind: "error"; message: string };

/**
 * "Reset demo patient": asks first, then calls POST /demo/reset.
 * Renders nothing when the server has no reset route.
 *
 * `variant="button"` is the clinician header control; `variant="link"` is the small
 * footer link on the demo patient's dashboard.
 */
export function DemoResetControl({
  variant,
  onReset,
  className,
}: {
  variant: "button" | "link";
  onReset: (result: DemoResetOut) => void;
  className?: string;
}) {
  const available = useAsync("demo-reset-available", (signal) => demoResetAvailable(signal));
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const descId = useId();

  if (available.data !== true) return null;

  async function confirm() {
    setPhase({ kind: "busy" });
    try {
      const result = await resetDemoPatient();
      setPhase({ kind: "idle" });
      onReset(result);
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 403
          ? "Ask the care team to reset the demo."
          : err instanceof ApiError && err.status === 404
            ? "The demo patient isn't on this server."
            : errorMessage(err);
      setPhase({ kind: "error", message });
    }
  }

  const open = phase.kind === "confirm" || phase.kind === "busy";

  return (
    <div className={cn("flex flex-col gap-2", variant === "link" ? "items-center text-center" : "items-start", className)}>
      {variant === "button" ? (
        <Button
          variant="danger-ghost"
          size="sm"
          onClick={() => setPhase(open ? { kind: "idle" } : { kind: "confirm" })}
          aria-expanded={open}
          aria-describedby={descId}
        >
          <RotateCcw className="size-4" aria-hidden="true" />
          Reset demo patient
        </Button>
      ) : (
        <button
          type="button"
          onClick={() => setPhase(open ? { kind: "idle" } : { kind: "confirm" })}
          aria-expanded={open}
          aria-describedby={descId}
          className="min-h-10 rounded-full px-3 text-xs font-bold text-brand-gray underline underline-offset-4 hover:text-brand-red-dark"
        >
          Reset the demo patient
        </button>
      )}
      <p id={descId} className={cn("max-w-xs text-xs text-brand-gray", !open && "sr-only")}>
        {DEMO_RESET_LABEL}.
      </p>
      {open ? (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Confirm demo reset">
          <Button variant="danger" size="sm" onClick={() => void confirm()} disabled={phase.kind === "busy"}>
            {phase.kind === "busy" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
            {phase.kind === "busy" ? "Resetting…" : "Yes, reset for everyone"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setPhase({ kind: "idle" })} disabled={phase.kind === "busy"}>
            Cancel
          </Button>
        </div>
      ) : null}
      {phase.kind === "error" ? (
        <p role="alert" className="max-w-xs text-xs font-semibold text-brand-red-dark">
          {phase.message}
        </p>
      ) : null}
    </div>
  );
}

/** One-line summary of what a reset removed, for a toast. */
export function describeReset(result: DemoResetOut): string {
  const n = (k: string) => result.counts[k] ?? 0;
  const parts = [
    `${n("chat_messages")} messages`,
    `${n("escalations")} alerts`,
    `${n("symptom_logs")} check-ins`,
  ];
  return `Cleared ${parts.join(", ")}.`;
}
