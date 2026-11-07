import { cn } from "@/lib/cn";

/** Live-text wordmark: "Cloud" in brand red, "Care" in brand cyan. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("font-extrabold tracking-tight whitespace-nowrap", className)}>
      <span className="text-brand-red">Cloud</span>
      <span className="text-brand-cyan">Care</span>
    </span>
  );
}

/** The slogan, always as live text. */
export const SLOGAN_LEAD = "Your head’s in the clouds.";
export const SLOGAN_TAIL = "Your care shouldn’t be.";

export function Slogan({ className }: { className?: string }) {
  return (
    <p className={cn("font-semibold italic text-brand-cyan-strong", className)}>
      {SLOGAN_LEAD} <span className="whitespace-nowrap">{SLOGAN_TAIL}</span>
    </p>
  );
}
