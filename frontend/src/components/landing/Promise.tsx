import { BookOpenCheck, CircleSlash, Pill, Send, Siren, UsersRound } from "lucide-react";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";

const PROMISES = [
  {
    icon: BookOpenCheck,
    title: "Answers only from your care plan",
    body: "Every answer shows the section it came from, so you and your clinician can check it.",
  },
  {
    icon: CircleSlash,
    title: "Declines what it doesn’t know",
    body: "If a question isn’t covered, Foggy says so, doesn’t guess, and logs it for your care team.",
  },
  {
    icon: Pill,
    title: "Never changes a dose",
    body: "Medication changes come from your clinician, never from an AI.",
  },
  {
    icon: Siren,
    title: "Red flags skip the AI",
    body: "Chest pain or trouble breathing gets an immediate “call 911” and alerts the team.",
  },
  {
    icon: UsersRound,
    title: "Humans close every escalation",
    body: "A clinician acknowledges and resolves each alert. The risk model ranks, people decide.",
  },
];

export function OurPromise() {
  return (
    <section id="our-promise" aria-labelledby="promise-title" className="scroll-mt-20 py-20 sm:py-28">
      <div className="mx-auto grid max-w-6xl items-start gap-12 px-4 sm:px-6 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
        <div className="lg:sticky lg:top-28">
          <p className="text-sm font-extrabold tracking-[0.14em] text-brand-red uppercase">Our ethical-AI promise</p>
          <h2 id="promise-title" className="mt-3 text-3xl leading-tight font-black tracking-tight text-balance text-ink sm:text-5xl">
            Foggy knows what it doesn&rsquo;t know.
          </h2>
          <p className="mt-5 max-w-lg text-lg leading-relaxed text-ink-soft">
            A recovery companion should be humble by design. Foggy is grounded in the instructions your clinician wrote,
            and it hands off to a person the moment it reaches the edge of them.
          </p>

          {/* Example of a declined question */}
          <div aria-hidden="true" className="mt-8 max-w-md rounded-[2rem] bg-surface-soft p-5 ring-1 ring-line">
            <div className="flex justify-end">
              <p className="max-w-[80%] rounded-[1.25rem] rounded-br-md bg-brand-cyan px-4 py-2.5 text-[0.95rem] text-white">
                Can I take ibuprofen with my aspirin?
              </p>
            </div>
            <div className="mt-3 flex items-end gap-2">
              <FoggyAvatar decorative />
              <div className="flex flex-col items-start gap-1.5">
                <p className="max-w-[90%] rounded-[1.25rem] rounded-bl-md bg-white px-4 py-2.5 text-[0.95rem] text-ink ring-1 ring-line">
                  That isn&rsquo;t in your care plan, so I won&rsquo;t guess. I&rsquo;ve sent your question to your care team.
                </p>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-pale px-2.5 py-1 text-xs font-bold text-brand-cyan-strong">
                  <Send className="size-3.5" />
                  Sent to your care team
                </span>
              </div>
            </div>
          </div>
        </div>

        <ul className="grid gap-4">
          {PROMISES.map((p) => (
            <li key={p.title} className="flex gap-4 rounded-[1.75rem] bg-white p-5 ring-1 ring-line sm:p-6">
              <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-surface-pale text-brand-cyan-strong">
                <p.icon className="size-6" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-lg font-extrabold text-ink">{p.title}</h3>
                <p className="mt-1 leading-relaxed text-ink-soft">{p.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
