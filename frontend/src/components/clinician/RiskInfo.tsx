"use client";

import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

export const RISK_EXPLAINER =
  "Estimate from the risk model at the patient's last check-in. Factor weights are relative: they show how much each factor pushed this estimate up, not percentages. Experimental, trained on synthetic data. Not a diagnosis.";

const WIDTH = 272; // px, matches w-68

/**
 * Info icon that explains the risk score. Opens on hover, keyboard focus or tap.
 * The bubble is position: fixed so table scrollers and dialogs don't clip it.
 */
export function RiskInfo({ label = "About the risk estimate" }: { label?: string }) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const [pinned, setPinned] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const tipId = useId();

  function show() {
    const r = btn.current?.getBoundingClientRect();
    if (!r) return;
    const left = Math.min(Math.max(8, r.left + r.width / 2 - WIDTH / 2), window.innerWidth - WIDTH - 8);
    setPos({ top: r.bottom + 6, left });
  }

  function hide() {
    if (!pinned) setPos(null);
  }

  // Anything that moves the icon closes the bubble; so does Escape or a tap elsewhere.
  useEffect(() => {
    if (!pos) return;
    const close = () => {
      setPinned(false);
      setPos(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // Close just the bubble, not the drawer around it.
        e.preventDefault();
        e.stopPropagation();
        close();
      }
    };
    const onPointer = (e: PointerEvent) => {
      if (!btn.current?.contains(e.target as Node)) close();
    };
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", onKey, true);
    window.addEventListener("pointerdown", onPointer);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", onKey, true);
      window.removeEventListener("pointerdown", onPointer);
    };
  }, [pos]);

  return (
    <>
      <button
        ref={btn}
        type="button"
        aria-label={label}
        aria-describedby={pos ? tipId : undefined}
        aria-expanded={pos !== null}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={(e) => {
          e.stopPropagation();
          if (pinned) {
            setPinned(false);
            setPos(null);
          } else {
            setPinned(true);
            show();
          }
        }}
        className="relative inline-grid size-6 shrink-0 place-items-center rounded-full text-brand-gray normal-case transition-colors before:absolute before:-inset-2 before:content-[''] hover:text-brand-cyan-strong"
      >
        <Info className="size-3.5" aria-hidden="true" />
      </button>
      {pos ? (
        <span
          id={tipId}
          role="tooltip"
          style={{ top: pos.top, left: pos.left, width: WIDTH }}
          className="fixed z-[60] rounded-2xl bg-ink px-3.5 py-2.5 text-left text-xs leading-relaxed font-semibold tracking-normal whitespace-normal text-white normal-case shadow-lift"
        >
          {RISK_EXPLAINER}
        </span>
      ) : null}
    </>
  );
}
