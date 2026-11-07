import { BellRing, CheckCircle2, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { CloudShape } from "@/components/brand/CloudShape";
import { Swoosh } from "@/components/brand/Swoosh";
import { SLOGAN_LEAD, SLOGAN_TAIL } from "@/components/brand/Wordmark";
import { ScriptedConversation } from "@/components/phone/ScriptedConversation";
import { DemoButton } from "./DemoProvider";

export function Hero() {
  return (
    <section aria-labelledby="hero-title" className="relative isolate overflow-hidden pb-16 sm:pb-24">
      {/* Atmosphere: soft pale-blue sky + drifting clouds */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[780px] bg-[radial-gradient(120%_70%_at_50%_0%,var(--surface-pale)_0%,rgb(229_244_248/0.55)_45%,transparent_75%)]"
      />
      <CloudShape className="pointer-events-none absolute top-24 -left-16 -z-10 w-56 animate-drift opacity-90 sm:left-[6%] sm:w-72" fill="#ffffff" />
      <CloudShape className="pointer-events-none absolute top-[26rem] -right-20 -z-10 w-64 animate-drift opacity-90 [animation-delay:-6s] sm:right-[5%] sm:w-80" fill="#ffffff" />
      <CloudShape className="pointer-events-none absolute top-[44rem] left-[8%] -z-10 hidden w-40 animate-drift [animation-delay:-3s] lg:block" />

      <div className="mx-auto flex max-w-6xl flex-col items-center px-4 pt-10 text-center sm:px-6 sm:pt-16">
        <p className="inline-flex items-center gap-2 rounded-full bg-white px-3.5 py-1.5 text-sm font-bold text-brand-cyan-strong shadow-soft ring-1 ring-line">
          <span className="size-2 rounded-full bg-brand-red" aria-hidden="true" />
          Post-op recovery companion
        </p>

        <h1
          id="hero-title"
          className="mt-6 max-w-4xl text-[2.6rem] leading-[1.04] font-black tracking-[-0.02em] text-balance text-ink sm:text-6xl lg:text-[4.6rem]"
        >
          The recovery plan that remembers for you.
        </h1>

        <div className="mt-5 flex flex-col items-center">
          <p className="text-xl font-bold text-brand-cyan-strong italic sm:text-2xl">
            {SLOGAN_LEAD} <span className="whitespace-nowrap">{SLOGAN_TAIL}</span>
          </p>
          <Swoosh className="mt-1 h-3 w-56 sm:h-4 sm:w-80" />
        </div>

        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-soft text-pretty sm:text-xl">
          Anesthesia fog makes discharge instructions easy to forget. Foggy texts and talks you through the plan your
          care team wrote, and brings a real person in whenever something isn&rsquo;t right.
        </p>

        <div className="mt-8 flex w-full flex-col items-stretch justify-center gap-3 sm:w-auto sm:flex-row sm:items-center">
          <DemoButton kind="chat" />
          <DemoButton kind="voice" />
        </div>

        <div className="relative mt-14 sm:mt-16">
          <FloatingNote
            className="top-24 -left-64 hidden lg:flex"
            icon={<CheckCircle2 className="size-5 text-ok" aria-hidden="true" />}
            title="Check-in logged"
            body="Pain 4/10 · risk low"
          />
          <FloatingNote
            className="top-[19rem] -right-72 hidden lg:flex"
            icon={<BellRing className="size-5 text-brand-red" aria-hidden="true" />}
            title="Dr. Patel’s team notified"
            body="Question not in the care plan"
          />
          <FloatingNote
            className="bottom-28 -left-72 hidden lg:flex"
            icon={<ShieldCheck className="size-5 text-brand-cyan-strong" aria-hidden="true" />}
            title="Answered from your plan"
            body="Cited: Wound care"
          />
          <ScriptedConversation />
        </div>
      </div>
    </section>
  );
}

function FloatingNote({
  className,
  icon,
  title,
  body,
}: {
  className?: string;
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={`absolute z-10 w-60 items-start gap-3 rounded-3xl bg-white/95 p-4 text-left shadow-lift ring-1 ring-line ${className ?? ""}`}
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-2xl bg-surface-pale">{icon}</span>
      <span>
        <span className="block text-sm font-extrabold text-ink">{title}</span>
        <span className="block text-xs text-brand-gray">{body}</span>
      </span>
    </div>
  );
}
