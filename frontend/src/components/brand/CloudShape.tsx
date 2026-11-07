import { cn } from "@/lib/cn";

/** Soft decorative cloud silhouette (not the logo). */
export function CloudShape({ className, fill = "var(--surface-pale)" }: { className?: string; fill?: string }) {
  return (
    <svg viewBox="0 0 200 100" aria-hidden="true" focusable="false" className={cn("block", className)}>
      <path
        fill={fill}
        d="M40 92C18 92 6 78 8 62c2-16 16-24 30-22 4-18 22-30 42-28 18 2 30 14 34 26 8-8 22-10 34-4 14 6 20 20 16 30 16 2 28 12 26 22-1 4-4 6-10 6Z"
      />
    </svg>
  );
}
