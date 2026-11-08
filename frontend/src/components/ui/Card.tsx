import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";

/** `flush` drops the built-in padding (cn() concatenates, so a "p-0" className can't override it). */
export function Card({ className, flush = false, ...props }: ComponentProps<"section"> & { flush?: boolean }) {
  return (
    <section
      className={cn("rounded-[1.75rem] bg-white shadow-soft ring-1 ring-line/70", !flush && "p-5 sm:p-6", className)}
      {...props}
    />
  );
}

type CardHeaderProps = {
  title: ReactNode;
  icon?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  id?: string;
  className?: string;
};

export function CardHeader({ title, icon, description, action, id, className }: CardHeaderProps) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-2xl bg-surface-pale text-brand-cyan-strong">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <h2 id={id} className="text-lg leading-tight font-extrabold text-ink">
            {title}
          </h2>
          {description ? <p className="mt-0.5 text-sm text-brand-gray">{description}</p> : null}
        </div>
      </div>
      {action ? <div className="max-w-full shrink-0">{action}</div> : null}
    </div>
  );
}
