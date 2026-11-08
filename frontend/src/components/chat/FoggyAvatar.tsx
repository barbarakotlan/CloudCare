import { FoggyFace } from "@/components/brand/FoggyFace";

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
 * Foggy's face: the pale-blue cloud with eyes (it blinks now and then), shown
 * on its own with no badge behind it. Used wherever Foggy speaks; the red
 * CloudMark stays the brand symbol and public/brand/foggy.png stays for icons.
 */
export function FoggyAvatar({ className, size = 32, decorative = false }: FoggyAvatarProps) {
  return <FoggyFace size={size} decorative={decorative} className={className} />;
}
