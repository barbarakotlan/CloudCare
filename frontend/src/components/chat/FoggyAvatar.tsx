import Image from "next/image";
import { cn } from "@/lib/cn";

type FoggyAvatarProps = {
  className?: string;
  /** Width and height in px. Designed for 24 to 96. */
  size?: number;
  /**
   * Hide the avatar from assistive tech when the name "Foggy" is already
   * announced next to it (chat headers, "Foggy said:" labels).
   */
  decorative?: boolean;
};

/**
 * Foggy's face: the pale-blue cloud from public/brand/foggy.png, shown on its
 * own with no badge behind it. Used wherever Foggy speaks; the red CloudMark
 * stays the brand symbol.
 */
export function FoggyAvatar({ className, size = 32, decorative = false }: FoggyAvatarProps) {
  return (
    <Image
      src="/brand/foggy.png"
      width={size}
      height={size}
      alt="Foggy"
      aria-hidden={decorative ? true : undefined}
      draggable={false}
      className={cn("pointer-events-none shrink-0 object-contain select-none", className)}
      style={{ width: size, height: size }}
    />
  );
}
