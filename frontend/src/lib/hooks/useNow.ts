"use client";

import { useSyncExternalStore } from "react";

const TICK_MS = 15_000;
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;
let current = 0;

function tick() {
  current = Math.floor(Date.now() / TICK_MS) * TICK_MS;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!timer) timer = setInterval(tick, TICK_MS);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

function getSnapshot() {
  const rounded = Math.floor(Date.now() / TICK_MS) * TICK_MS;
  if (rounded !== current) current = rounded;
  return current;
}

/**
 * Current time (ms), refreshed every 15 s. Returns null during prerender and
 * hydration so server HTML never depends on the clock.
 */
export function useNow(): number | null {
  return useSyncExternalStore(subscribe, getSnapshot, () => null);
}
