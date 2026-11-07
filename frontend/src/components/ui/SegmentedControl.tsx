"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type SegmentOption<T extends string> = { value: T; label: ReactNode; icon?: ReactNode };

/**
 * Accessible segmented control (radiogroup semantics, arrow-key navigation,
 * roving tabindex).
 */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
  size = "md",
  fullWidth = true,
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
  size?: "sm" | "md";
  fullWidth?: boolean;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (index + 1) % options.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (index - 1 + options.length) % options.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = options.length - 1;
    else return;
    e.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn("inline-flex gap-1 rounded-full bg-surface-pale p-1", fullWidth && "w-full", className)}
    >
      {options.map((opt, i) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              "inline-flex flex-1 items-center justify-center gap-2 rounded-full font-bold transition-[background-color,color,box-shadow] duration-200",
              size === "md" ? "h-11 px-4 text-[0.95rem]" : "h-8 px-3 text-sm",
              selected
                ? "bg-white text-brand-cyan-strong shadow-[0_2px_8px_-2px_rgb(19_126_160/0.3)]"
                : "text-ink-soft hover:text-ink",
            )}
          >
            {opt.icon}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
