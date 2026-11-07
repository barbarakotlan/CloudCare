import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** CSS-only iPhone mockup. Children render inside the screen below the status bar. */
export function IPhoneFrame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "relative aspect-[9/18.6] w-[min(78vw,300px)] rounded-[3rem] bg-[#18212b] p-[10px] shadow-phone ring-1 ring-black/40 sm:w-[320px]",
        className,
      )}
    >
      {/* side buttons */}
      <span aria-hidden="true" className="absolute top-28 -left-[3px] h-10 w-[3px] rounded-l bg-[#2a3542]" />
      <span aria-hidden="true" className="absolute top-40 -left-[3px] h-14 w-[3px] rounded-l bg-[#2a3542]" />
      <span aria-hidden="true" className="absolute top-36 -right-[3px] h-20 w-[3px] rounded-r bg-[#2a3542]" />

      <div className="relative flex h-full flex-col overflow-hidden rounded-[2.4rem] bg-white">
        {/* status bar + dynamic island */}
        <div aria-hidden="true" className="relative flex h-11 shrink-0 items-center justify-between px-7 pt-1 text-[0.78rem] font-bold text-ink">
          <span>9:41</span>
          <span className="absolute top-2.5 left-1/2 h-[26px] w-[92px] -translate-x-1/2 rounded-full bg-[#0d1319]" />
          <span className="flex items-center gap-1">
            <span className="flex items-end gap-[2px]">
              <span className="h-[5px] w-[3px] rounded-sm bg-ink" />
              <span className="h-[7px] w-[3px] rounded-sm bg-ink" />
              <span className="h-[9px] w-[3px] rounded-sm bg-ink" />
              <span className="h-[11px] w-[3px] rounded-sm bg-ink" />
            </span>
            <span className="ml-1 inline-flex h-[11px] w-[22px] items-center rounded-[3px] border border-ink/70 p-[1.5px]">
              <span className="h-full w-[75%] rounded-[1.5px] bg-ink" />
            </span>
          </span>
        </div>
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        <span aria-hidden="true" className="mx-auto mb-2 h-[5px] w-28 shrink-0 rounded-full bg-ink/80" />
      </div>
    </div>
  );
}
