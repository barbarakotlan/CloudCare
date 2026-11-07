import Image from "next/image";
import { cn } from "@/lib/cn";

type FoggyAvatarProps = {
  className?: string;
  /** Outer diameter in px. Designed for 24 to 96. */
  size?: number;
  /**
   * Hide the avatar from assistive tech when the name "Foggy" is already
   * announced next to it (chat headers, "Foggy said:" labels).
   */
  decorative?: boolean;
};

/**
 * Foggy's face: the pale-blue cloud from public/brand/foggy.png in a soft
 * circular badge. Used wherever Foggy speaks; the red CloudMark stays the
 * brand symbol.
 */
export function FoggyAvatar({ className, size = 32, decorative = false }: FoggyAvatarProps) {
  // The cloud spans almost the full width of its square canvas, so inset it
  // enough to clear the circle's edge. Square in, square out: never distorted.
  const face = Math.round(size * 0.8);
  return (
    <span
      aria-hidden={decorative ? true : undefined}
      className={cn(
        "inline-grid shrink-0 place-items-center overflow-hidden rounded-full border border-brand-cyan/30 bg-surface-pale",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <Image
        src="/brand/foggy.png"
        width={face}
        height={face}
        alt="Foggy"
        draggable={false}
        className="pointer-events-none object-contain select-none"
        style={{ width: face, height: face }}
      />
    </span>
  );
}
