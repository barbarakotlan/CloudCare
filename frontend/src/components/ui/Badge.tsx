import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type BadgeTone = "cyan" | "red" | "orange" | "amber" | "gray" | "green" | "pale";

const tones: Record<BadgeTone, string> = {
  cyan: "bg-brand-cyan/12 text-brand-cyan-strong ring-brand-cyan/25",
  red: "bg-brand-red/10 text-brand-red-dark ring-brand-red/30",
  orange: "bg-sev-high/12 text-[#a84d0c] ring-sev-high/30",
  amber: "bg-sev-medium/14 text-[#7d5600] ring-sev-medium/30",
  gray: "bg-sev-low/12 text-[#4c5560] ring-sev-low/25",
  green: "bg-ok/12 text-[#146b49] ring-ok/25",
  pale: "bg-surface-pale text-brand-cyan-strong ring-transparent",
};

export function Badge({
  tone = "cyan",
  children,
  className,
  dot = false,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold whitespace-nowrap ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {dot ? <span aria-hidden="true" className="size-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}
