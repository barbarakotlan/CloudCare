import { ClipboardPenLine, MessageCircleHeart, UserRoundCheck } from "lucide-react";
import { WaveDivider } from "@/components/brand/Swoosh";

const STEPS = [
  {
    icon: ClipboardPenLine,
    title: "Your clinician writes the plan",
    body: "Before discharge, the care team enters your recovery instructions: wound care, activity, medications, and when to call.",
  },
  {
    icon: MessageCircleHeart,
    title: "Foggy follows up at home",
    body: "Text or talk to Foggy, an automated assistant, any time. It answers from your plan, shows your reminders, and runs symptom check-ins. It can make mistakes, so keep your written plan handy.",
  },
  {
    icon: UserRoundCheck,
    title: "A human closes every loop",
    body: "For questions outside the plan, Foggy offers to message your care team and sends nothing without your OK. Red-flag symptoms get “Call 911 now,” and high-risk check-ins appear in your care team’s queue for a person to review.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-20">
      <WaveDivider />
      <div className="bg-surface-pale pt-10 pb-20 sm:pt-12 sm:pb-28">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-extrabold tracking-[0.14em] text-brand-cyan-strong uppercase">How it works</p>
            <h2 id="how-title" className="mt-3 text-3xl leading-tight font-black tracking-tight text-balance text-ink sm:text-5xl">
              From the recovery room to your living room.
            </h2>
          </div>

          <ol className="relative mt-12 grid gap-5 sm:mt-16 md:grid-cols-3 md:gap-6">
            {/* connecting swoosh line behind the cards on desktop */}
            <svg
              aria-hidden="true"
              viewBox="0 0 1000 60"
              preserveAspectRatio="none"
              className="absolute top-14 left-[12%] hidden h-12 w-[76%] md:block"
            >
              <path d="M0 40 C 250 0, 500 60, 1000 18" fill="none" stroke="var(--brand-cyan)" strokeWidth="2.5" strokeDasharray="2 10" strokeLinecap="round" />
            </svg>
            {STEPS.map((step, i) => (
              <li key={step.title} className="relative rounded-[2rem] bg-white p-7 shadow-soft">
                <div className="flex items-center gap-3">
                  <span className="grid size-14 place-items-center rounded-[1.25rem] bg-surface-pale text-brand-cyan-strong">
                    <step.icon className="size-7" aria-hidden="true" />
                  </span>
                  <span className="text-sm font-extrabold text-brand-gray">Step {i + 1}</span>
                </div>
                <h3 className="mt-5 text-xl font-extrabold text-ink">{step.title}</h3>
                <p className="mt-2 leading-relaxed text-ink-soft">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <WaveDivider flip />
    </section>
  );
}
