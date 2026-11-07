import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";

const field =
  // 16 px text on phones so iOS doesn't zoom the page when a field gets focus.
  "w-full rounded-2xl border border-line bg-white px-4 text-base sm:text-[0.98rem] text-ink placeholder:text-brand-gray/70 transition-colors hover:border-brand-cyan/60 focus:border-brand-cyan focus:outline-none focus-visible:outline-2 focus-visible:outline-brand-cyan/40 disabled:bg-surface-soft";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(field, "h-12", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn(field, "h-12 pr-10", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cn(field, "py-3 leading-relaxed", className)} {...props} />;
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
  className,
}: {
  label: ReactNode;
  htmlFor: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-sm font-bold text-ink-soft">
        {label}
      </label>
      {children}
      {hint ? <p className="text-xs text-brand-gray">{hint}</p> : null}
    </div>
  );
}
