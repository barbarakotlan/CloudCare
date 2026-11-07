import Image from "next/image";
import { cn } from "@/lib/cn";
import { Wordmark } from "./Wordmark";

type CloudMarkProps = {
  /** Rendered width in px; height follows the symbol's 1988x962 aspect ratio. */
  size?: number;
  className?: string;
  /** Empty by default because the mark is usually next to the live-text wordmark. */
  alt?: string;
  preload?: boolean;
};

/** The red cloud-with-heart symbol from frontend/public/brand. */
export function CloudMark({ size = 40, className, alt = "", preload = false }: CloudMarkProps) {
  const height = Math.round((size * 962) / 1988);
  return (
    <Image
      src="/brand/cloudcare-symbol.png"
      width={size}
      height={height}
      alt={alt}
      preload={preload}
      className={cn("select-none", className)}
      style={{ width: size, height: "auto" }}
    />
  );
}

/** Symbol + live wordmark, used in headers. */
export function BrandLockup({ className, size = 40 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <CloudMark size={size} preload />
      <Wordmark className="text-[1.4rem] leading-none" />
    </span>
  );
}
