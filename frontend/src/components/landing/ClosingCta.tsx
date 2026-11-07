import { CloudMark } from "@/components/brand/CloudMark";
import { CloudShape } from "@/components/brand/CloudShape";
import { Swoosh } from "@/components/brand/Swoosh";
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
        <div className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
          <DemoButton kind="chat" />
          <DemoButton kind="voice" />
        </div>
      </div>
    </section>
  );
}
