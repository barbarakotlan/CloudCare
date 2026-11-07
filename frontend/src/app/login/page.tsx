import type { Metadata } from "next";
import Link from "next/link";
import { BrandLockup, CloudMark } from "@/components/brand/CloudMark";
import { CloudShape } from "@/components/brand/CloudShape";
import { Swoosh } from "@/components/brand/Swoosh";
import { SLOGAN_LEAD, SLOGAN_TAIL } from "@/components/brand/Wordmark";
import { LoginForm } from "@/components/app/LoginForm";

export const metadata: Metadata = {
  title: "Log in",
  description: "Sign in to CloudCare as a patient or a member of the care team.",
};

export default function LoginPage() {
  return (
    <div className="grid min-h-dvh flex-1 lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel (desktop) */}
      <aside className="relative isolate hidden overflow-hidden bg-surface-pale lg:flex lg:flex-col lg:justify-between lg:p-12">
        <CloudShape className="absolute top-20 -left-16 -z-10 w-72 animate-drift" fill="#ffffff" />
        <CloudShape className="absolute right-[-4rem] bottom-32 -z-10 w-96 animate-drift [animation-delay:-5s]" fill="#ffffff" />
        <Link href="/" className="self-start rounded-xl" aria-label="CloudCare home">
          <BrandLockup size={48} />
        </Link>
        <div className="max-w-md">
          <CloudMark size={140} />
          <p className="mt-8 text-4xl leading-tight font-black tracking-tight text-ink">
            {SLOGAN_LEAD}
            <br />
            <span className="text-brand-cyan-strong">{SLOGAN_TAIL}</span>
          </p>
          <Swoosh className="mt-3 h-4 w-72" />
          <p className="mt-6 text-lg leading-relaxed text-ink-soft">
            Patients get their care plan, reminders and Foggy. Care teams get a live queue of who needs them now.
          </p>
        </div>
      </aside>

      {/* Form */}
      <main id="main" className="flex flex-col px-4 py-6 sm:px-8 sm:py-10">
        <Link href="/" className="self-start rounded-xl lg:hidden" aria-label="CloudCare home">
          <BrandLockup size={40} />
        </Link>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <h1 className="text-3xl font-black tracking-tight text-ink sm:text-4xl">Welcome back</h1>
          <p className="mt-2 text-ink-soft">Choose how you&rsquo;re signing in.</p>
          <LoginForm />
          <p className="mt-6 text-center text-sm text-brand-gray">
            By signing in you agree to our{" "}
            <Link
              href="/terms"
              className="font-bold text-brand-cyan-strong underline decoration-brand-cyan/40 underline-offset-2 hover:decoration-brand-cyan-strong"
            >
              Terms
            </Link>
            .
          </p>
        </div>
      </main>
    </div>
  );
}
