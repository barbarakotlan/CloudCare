import { cn } from "@/lib/cn";

/**
 * The tapered brush swoosh from the wordmark: thin on the left,
 * sweeping right and hooking up at the end. Decorative.
 */
export function Swoosh({ className, color = "var(--brand-red)" }: { className?: string; color?: string }) {
  return (
    <svg
      viewBox="0 0 200 40"
      aria-hidden="true"
      focusable="false"
      className={cn("block", className)}
      preserveAspectRatio="none"
    >
      <path
        fill={color}
        d="M3 35.5C26 21 70 15.5 120 19.5c26 2 48 6.6 63-1.2 6.2-3.3 9.5-9.4 10.5-14.2.4-2 3.2-2.6 4.6-.8 1.7 2.2 1.9 5.6.4 9.5-3.6 9.4-14.6 17-34.5 17.4-19.6.4-39.4-4.9-63.6-6.4C66 22.4 30 26 6.3 37.6 4 38.7 1.6 36.9 3 35.5Z"
      />
    </svg>
  );
}

/** Gentle wave used to transition between white and pale-blue sections. */
export function WaveDivider({
  className,
  fill = "var(--surface-pale)",
  flip = false,
}: {
  className?: string;
  fill?: string;
  flip?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 1440 80"
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="none"
      className={cn("block h-10 w-full sm:h-16", flip && "rotate-180", className)}
    >
      <path
        fill={fill}
        d="M0 56C180 18 380 6 620 26s420 46 620 28c90-8 150-22 200-34V80H0Z"
      />
    </svg>
  );
}
