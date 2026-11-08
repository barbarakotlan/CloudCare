import type { Metadata } from "next";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { TeamGrid } from "@/components/landing/TeamGrid";

export const metadata: Metadata = {
  title: "The team",
  description: "The three co-founders building CloudCare: Jacob Foti, Barbara Kotlan and Anna Kotlan.",
};

export default function TeamPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="flex-1 bg-surface-soft">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-extrabold tracking-[0.14em] text-brand-cyan-strong uppercase">Who we are</p>
            <h1 className="mt-3 text-4xl leading-tight font-black tracking-tight text-balance text-ink sm:text-5xl">
              The team
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-pretty text-ink-soft">
              Three co-founders bringing the care team&rsquo;s recovery plan home with patients.
            </p>
          </div>
          <div className="mt-10 sm:mt-14">
            <TeamGrid />
          </div>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
