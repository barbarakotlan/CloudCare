"use client";

import { BookOpen, CheckCircle2, Pause, Play, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { cn } from "@/lib/cn";
import { LANDING_SCRIPT, type ScriptStep } from "@/lib/demo/foggyScript";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";
import { IPhoneFrame } from "./IPhoneFrame";

const GAP_BEFORE_MS = 750;
const LOOP_HOLD_MS = 4200;

function PhoneBubble({ step }: { step: ScriptStep }) {
  const mine = step.from === "patient";
  return (
    <div className={cn("flex animate-bubble-in flex-col gap-1", mine ? "items-end" : "items-start pl-[30px]")}>
      <div className={cn("relative", mine ? "max-w-[86%]" : "max-w-[92%]")}>
        {mine ? null : <FoggyAvatar size={24} decorative className="absolute bottom-0 -left-[30px]" />}
        <div
          className={cn(
            "rounded-[1.1rem] px-3 py-2 text-[0.8rem] leading-snug",
            mine ? "rounded-br-md bg-brand-cyan text-white" : "rounded-bl-md bg-surface-pale text-ink",
          )}
        >
          {step.text}
        </div>
      </div>
      {step.cite ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-[0.62rem] font-bold text-brand-cyan-strong ring-1 ring-brand-cyan/25">
          <BookOpen className="size-2.5" aria-hidden="true" />
          {step.cite}
        </span>
      ) : null}
      {step.status ? (
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.62rem] font-bold",
            step.status.tone === "care-team" ? "bg-brand-red/10 text-brand-red-dark" : "bg-ok/12 text-[#146b49]",
          )}
        >
          {step.status.tone === "care-team" ? (
            <Send className="size-2.5" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="size-2.5" aria-hidden="true" />
          )}
          {step.status.text}
        </span>
      ) : null}
    </div>
  );
}

/** The landing-page phone: a scripted Foggy conversation that types itself and loops. */
export function ScriptedConversation({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const [paused, setPaused] = useState(false);
  const [count, setCount] = useState(0);
  const [typing, setTyping] = useState(false);
  const animate = !reduced && !paused;
  const shown = reduced ? LANDING_SCRIPT.length : count;

  useEffect(() => {
    if (!animate) return;
    const timers: Array<ReturnType<typeof setTimeout>> = [];
    if (count < LANDING_SCRIPT.length) {
      const next = LANDING_SCRIPT[count];
      timers.push(
        setTimeout(() => {
          setTyping(next.from === "foggy");
          timers.push(
            setTimeout(() => {
              setTyping(false);
              setCount((c) => c + 1);
            }, next.typingMs),
          );
        }, GAP_BEFORE_MS),
      );
    } else {
      timers.push(setTimeout(() => setCount(0), LOOP_HOLD_MS));
    }
    return () => timers.forEach(clearTimeout);
  }, [count, animate]);

  return (
    <figure className={cn("flex flex-col items-center gap-4", className)}>
      <IPhoneFrame>
        <div className="flex items-center gap-2.5 border-b border-line/70 px-4 pt-1 pb-2.5">
          <FoggyAvatar size={34} decorative />
          <div className="min-w-0 leading-tight">
            <p className="text-[0.85rem] font-extrabold text-ink">Foggy</p>
            <p className="truncate text-[0.66rem] text-brand-gray">Replies from your care plan</p>
          </div>
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-ok/12 px-2 py-0.5 text-[0.6rem] font-bold text-[#146b49]">
            <span className="size-1.5 rounded-full bg-ok" aria-hidden="true" />
            Online
          </span>
        </div>
        <div aria-hidden="true" className="flex min-h-0 flex-1 flex-col justify-end gap-2.5 overflow-hidden px-3 pb-3">
          {LANDING_SCRIPT.slice(0, shown).map((step, i) => (
            <PhoneBubble key={`${i}-${step.text}`} step={step} />
          ))}
          {typing && animate ? (
            <div className="flex animate-bubble-in items-end gap-1.5 self-start">
              <FoggyAvatar size={24} decorative />
              <div className="flex gap-1 rounded-[1.1rem] rounded-bl-md bg-surface-pale px-3 py-2.5">
                {[0, 160, 320].map((d) => (
                  <span key={d} className="size-1.5 animate-typing rounded-full bg-brand-cyan" style={{ animationDelay: `${d}ms` }} />
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <div aria-hidden="true" className="mx-3 mb-2 flex h-9 items-center rounded-full border border-line px-3 text-[0.72rem] text-brand-gray">
          Text Foggy…
        </div>
      </IPhoneFrame>

      <figcaption className="sr-only">
        Example conversation with Foggy:{" "}
        {LANDING_SCRIPT.map((s) => `${s.from === "foggy" ? "Foggy" : "Patient"}: ${s.text}`).join(" ")}
      </figcaption>

      {!reduced ? (
        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold text-brand-gray transition-colors hover:bg-surface-pale hover:text-ink"
        >
          {paused ? <Play className="size-3.5" aria-hidden="true" /> : <Pause className="size-3.5" aria-hidden="true" />}
          {paused ? "Play conversation" : "Pause conversation"}
        </button>
      ) : null}
    </figure>
  );
}
