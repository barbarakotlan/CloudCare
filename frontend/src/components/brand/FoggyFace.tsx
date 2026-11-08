"use client";

import { useEffect, useId, useState, type CSSProperties } from "react";
import { cn } from "@/lib/cn";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";

/** Cloud outline in a 100 × 100 box, traced from public/brand/foggy.png (bumps clockwise from the upper left). */
const CLOUD =
  "M15 41.4 A10.6 10.6 0 0 1 31.2 28 A19.5 19.5 0 0 1 68.8 27.4 A11.7 11.7 0 0 1 85 42.5 A16 16 0 0 1 82.8 74.2 A12.5 12.5 0 0 1 61.8 82.3 A19.8 19.8 0 0 1 38.7 82.3 A14.4 14.4 0 0 1 16.7 74.2 A16.7 16.7 0 0 1 15 41.4 Z";

const EYES = [
  { cx: 34.9, cy: 55.2 },
  { cx: 64.5, cy: 55.2 },
];
const EYE_RX = 4.3;
const EYE_RY = 5.4;

const CLOSE_MS = 70; // lids travel time
const HOLD_MS = 60; // fully closed
const DOUBLE_GAP_MS = 170; // between the two blinks of a double blink

/**
 * Blink schedule: one blink every 4 to 7 s, with roughly one in five being a
 * double blink. Off under prefers-reduced-motion and while the tab is hidden.
 */
function useBlink(enabled: boolean): boolean {
  const [closed, setClosed] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const timers = new Set<number>();
    const later = (fn: () => void, ms: number) => {
      const id = window.setTimeout(() => {
        timers.delete(id);
        fn();
      }, ms);
      timers.add(id);
    };
    const clear = () => {
      timers.forEach((id) => window.clearTimeout(id));
      timers.clear();
      setClosed(false);
    };

    const blinkOnce = (then: () => void) => {
      setClosed(true);
      later(() => {
        setClosed(false);
        later(then, CLOSE_MS);
      }, CLOSE_MS + HOLD_MS);
    };
    const schedule = () => {
      later(() => {
        const double = Math.random() < 0.2;
        blinkOnce(() => (double ? later(() => blinkOnce(schedule), DOUBLE_GAP_MS) : schedule()));
      }, 4000 + Math.random() * 3000);
    };

    const onVisibility = () => {
      clear();
      if (document.visibilityState === "visible") schedule();
    };

    if (document.visibilityState === "visible") schedule();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [enabled]);

  return enabled && closed;
}

type FoggyFaceProps = {
  /** Width and height in px. Looks right from 24 to 96. */
  size?: number;
  className?: string;
  /** Accessible name; ignored when `decorative`. */
  label?: string;
  /** Hide from assistive tech (the name "Foggy" is already announced nearby). */
  decorative?: boolean;
  /** Set false for a still face (e.g. thumbnails). */
  blink?: boolean;
};

/**
 * Foggy as an inline SVG: the pale-blue cloud with two black oval eyes from
 * public/brand/foggy.png (the PNG stays for favicon and social images).
 * Eyelids filled with the cloud's own gradient close over the eyes to blink.
 */
export function FoggyFace({ size = 32, className, label = "Foggy", decorative = false, blink = true }: FoggyFaceProps) {
  const reduced = useReducedMotion();
  const closed = useBlink(blink && !reduced);
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const fill = `foggy-fill-${uid}`;
  const clip = `foggy-clip-${uid}`;

  // Keep the outline about 1 px wide on screen at every size (the PNG's is ~0.9% of the width).
  const stroke = Math.max(0.95, 95 / size);
  const detailed = size >= 40;

  const lid = (origin: "top" | "bottom"): CSSProperties => ({
    transformBox: "fill-box",
    transformOrigin: origin,
    transform: closed ? "scaleY(1)" : "scaleY(0)",
    transition: `transform ${CLOSE_MS}ms ${closed ? "ease-in" : "ease-out"}`,
  });

  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative ? true : undefined}
      focusable="false"
      className={cn("pointer-events-none shrink-0 select-none", className)}
      style={{ width: size, height: size }}
    >
      <defs>
        {/* userSpaceOnUse so the eyelids pick up exactly the colour behind each eye. */}
        <linearGradient id={fill} gradientUnits="userSpaceOnUse" x1="12" y1="14" x2="92" y2="88">
          <stop offset="0" stopColor="#EEF6FE" />
          <stop offset="0.55" stopColor="#D8EAFB" />
          <stop offset="1" stopColor="#B9DAF7" />
        </linearGradient>
        <clipPath id={clip}>
          <path d={CLOUD} />
        </clipPath>
      </defs>

      <path d={CLOUD} fill={`url(#${fill})`} />
      {detailed ? (
        // Soft white rim inside the upper-left edge, like the PNG's highlight.
        <path
          d={CLOUD}
          fill="none"
          stroke="#FFFFFF"
          strokeOpacity={0.75}
          strokeWidth={3}
          transform="translate(1.1 1.1)"
          clipPath={`url(#${clip})`}
        />
      ) : null}
      <path d={CLOUD} fill="none" stroke="#5DA5E8" strokeWidth={stroke} strokeLinejoin="round" />

      {EYES.map(({ cx, cy }) => (
        <g key={cx}>
          <ellipse cx={cx} cy={cy} rx={EYE_RX} ry={EYE_RY} fill="#222222" />
          {/* Lids stop just short of the middle, leaving a thin closed-eye line. */}
          <rect
            x={cx - EYE_RX - 0.8}
            y={cy - EYE_RY - 0.8}
            width={EYE_RX * 2 + 1.6}
            height={EYE_RY + 0.8 - 0.45}
            fill={`url(#${fill})`}
            style={lid("top")}
          />
          <rect
            x={cx - EYE_RX - 0.8}
            y={cy + 0.45}
            width={EYE_RX * 2 + 1.6}
            height={EYE_RY + 0.8 - 0.45}
            fill={`url(#${fill})`}
            style={lid("bottom")}
          />
        </g>
      ))}
    </svg>
  );
}
