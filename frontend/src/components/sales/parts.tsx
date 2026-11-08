import Image from "next/image";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { BARBARA_PHOTO } from "./salesStorage";

/** Barbara's photo in a circle with a light brand ring. */
export function BarbaraPhoto({
  size = 40,
  ring = true,
  className,
}: {
  size?: number;
  /** The light ring; off when the parent draws its own. */
  ring?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "relative block shrink-0 overflow-hidden rounded-full bg-[radial-gradient(circle_at_50%_35%,#ffffff_0%,var(--surface-pale)_60%,#cfe9f2_100%)]",
        ring && "ring-2 ring-[#bfe3ee]",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <Image
        src={BARBARA_PHOTO}
        alt=""
        width={size * 2}
        height={size * 2}
        loading="eager"
        draggable={false}
        className="size-full object-cover object-[50%_20%] select-none [-webkit-touch-callout:none]"
      />
    </span>
  );
}

/** One of Barbara's chat bubbles, with her photo beside the first in a run. */
export function BarbaraBubble({
  children,
  showAvatar = true,
  className,
}: {
  children: ReactNode;
  showAvatar?: boolean;
  className?: string;
}) {
  return (
    <div className="flex animate-bubble-in items-end gap-2">
      {showAvatar ? <BarbaraPhoto size={28} /> : <span className="w-7 shrink-0" aria-hidden="true" />}
      <div className="flex max-w-[85%] min-w-0 flex-col gap-2">
        <span className="sr-only">Barbara said:</span>
        <div
          className={cn(
            "rounded-[1.25rem] rounded-bl-md bg-surface-pale px-4 py-2.5 text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap text-ink",
            className,
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

/** The visitor's bubble (right-aligned, cyan). */
export function VisitorBubble({
  children,
  failed = false,
  after,
}: {
  children: ReactNode;
  failed?: boolean;
  after?: ReactNode;
}) {
  return (
    <div className="flex animate-bubble-in flex-col items-end gap-1">
      <span className="sr-only">You said:</span>
      <div
        className={cn(
          "max-w-[85%] rounded-[1.25rem] rounded-br-md bg-brand-cyan px-4 py-2.5 text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap text-white",
          failed && "opacity-60",
        )}
      >
        {children}
      </div>
      {after}
    </div>
  );
}
