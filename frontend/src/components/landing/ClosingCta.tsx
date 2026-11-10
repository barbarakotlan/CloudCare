import Link from "next/link";
import { CloudMark } from "@/components/brand/CloudMark";
import { CloudShape } from "@/components/brand/CloudShape";
import { Swoosh } from "@/components/brand/Swoosh";
import { VOICE_ENABLED } from "@/components/voice/voiceEnabled";
import { DemoButton } from "./DemoProvider";

export function ClosingCta() {
  return (
    <section aria-labelledby="closing-title" className="px-4 pb-20 sm:px-6 sm:pb-28">
      <div className="relative isolate mx-auto max-w-5xl overflow-hidden rounded-[2.5rem] bg-surface-pale px-6 py-14 text-center sm:px-12 sm:py-20">
        <CloudShape className="absolute -top-6 -left-10 -z-10 w-52 opacity-90" fill="#ffffff" />
        <CloudShape className="absolute -right-12 -bottom-8 -z-10 w-64 opacity-90" fill="#ffffff" />
        <CloudMark size={88} className="mx-auto" />
        <h2 id="closing-title" className="mx-auto mt-6 max-w-2xl text-3xl leading-tight font-black tracking-tight text-balance text-ink sm:text-5xl">
          Recovery happens at home. Foggy keeps it on plan.
        </h2>
        <Swoosh className="mx-auto mt-3 h-3 w-48 sm:h-4 sm:w-64" />
        {VOICE_ENABLED ? (
          <div className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
            <DemoButton kind="chat" />
            <DemoButton kind="voice" />
          </div>
        ) : (
          <div className="mt-8 flex justify-center">
            <DemoButton kind="chat" />
          </div>
        )}
        <p className="mx-auto mt-5 max-w-md text-sm leading-relaxed text-ink-soft">
          The demos use a sample care plan, so please don&rsquo;t enter real health information. Read how we handle your information in our{" "}
          <Link href="/privacy" className="font-bold text-brand-cyan-strong underline underline-offset-2">
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </section>
  );
}
