import { ArrowRight, Check, HeartPulse, Stethoscope } from "lucide-react";
import { ButtonLink } from "@/components/ui/Button";

const PATIENT_FEATURES = [
  "Today’s plan in plain language",
  "Medication and appointment reminders",
  "Text or talk to Foggy, day or night",
  "Two-minute symptom check-ins",
];

const CLINICIAN_FEATURES = [
  "Live escalation queue, most urgent first",
  "Patients ranked by recovery risk",
  "Full chat transcripts and check-in history",
  "Upload or update a care plan in seconds",
];

export function Audiences() {
  return (
    <section aria-labelledby="audiences-title" className="pb-20 sm:pb-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <h2 id="audiences-title" className="sr-only">
          Built for both sides of discharge
        </h2>
        <div className="grid gap-5 md:grid-cols-2">
          <article className="relative overflow-hidden rounded-[2.25rem] bg-surface-pale p-7 sm:p-10">
            <span className="grid size-14 place-items-center rounded-[1.25rem] bg-white text-brand-red shadow-soft">
              <HeartPulse className="size-7" aria-hidden="true" />
            </span>
            <h3 className="mt-6 text-2xl font-black tracking-tight text-ink sm:text-3xl">For patients and families</h3>
            <p className="mt-2 text-ink-soft">Everything you were told at discharge, ready when you need it.</p>
            <ul className="mt-6 grid gap-2.5">
              {PATIENT_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 font-semibold text-ink">
                  <Check className="mt-0.5 size-5 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
                  {f}
                </li>
              ))}
            </ul>
            <ButtonLink href="/login" className="mt-8">
              Open the patient demo
              <ArrowRight className="size-4" aria-hidden="true" />
            </ButtonLink>
          </article>

          <article className="relative overflow-hidden rounded-[2.25rem] bg-white p-7 ring-1 ring-line sm:p-10">
            <span className="grid size-14 place-items-center rounded-[1.25rem] bg-surface-pale text-brand-cyan-strong">
              <Stethoscope className="size-7" aria-hidden="true" />
            </span>
            <h3 className="mt-6 text-2xl font-black tracking-tight text-ink sm:text-3xl">For care teams</h3>
            <p className="mt-2 text-ink-soft">See who needs you now, without reading every message.</p>
            <ul className="mt-6 grid gap-2.5">
              {CLINICIAN_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2.5 font-semibold text-ink">
                  <Check className="mt-0.5 size-5 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
                  {f}
                </li>
              ))}
            </ul>
            <ButtonLink href="/login" variant="secondary" className="mt-8">
              Open the clinician demo
              <ArrowRight className="size-4" aria-hidden="true" />
            </ButtonLink>
          </article>
        </div>
      </div>
    </section>
  );
}
