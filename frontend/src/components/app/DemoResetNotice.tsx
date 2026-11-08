"use client";

import { Info, X } from "lucide-react";
import { useEffect, useState } from "react";
import { demoResetWasMissed, noteDemoResetMissed } from "@/lib/api/demo";
import { cn } from "@/lib/cn";

/**
 * Quiet one-line notice on the demo patient's dashboard when the fresh-demo reset at
 * sign-in did not finish (slow or sleeping server). Shown once per sign-in.
 */
export function DemoResetNotice({ className }: { className?: string }) {
  // Read once on mount; the dashboard only renders on the client after the session check.
  const [show, setShow] = useState(() => typeof window !== "undefined" && demoResetWasMissed());

  // Clear the flag so a reload does not show it again.
  useEffect(() => {
    if (show) noteDemoResetMissed(false);
  }, [show]);

  if (!show) return null;
  return (
    <p
      role="status"
      className={cn(
        "flex items-center gap-2 rounded-2xl bg-white/70 py-1.5 pr-1.5 pl-3.5 text-sm text-ink-soft ring-1 ring-line/80",
        className,
      )}
    >
      <Info className="size-4 shrink-0 text-brand-gray" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        We couldn&rsquo;t reset the demo this time. Use <span className="font-semibold text-ink">Reset demo patient</span>{" "}
        on the clinician side.
      </span>
      <button
        type="button"
        onClick={() => setShow(false)}
        aria-label="Dismiss"
        className="grid size-8 shrink-0 place-items-center rounded-full text-brand-gray transition-colors hover:bg-surface-pale hover:text-ink"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </p>
  );
}
