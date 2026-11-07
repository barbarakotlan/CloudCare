"use client";

import { useEffect, useRef } from "react";

/**
 * Calls `fn` immediately, then every `intervalMs` while mounted and visible.
 * Also refreshes as soon as the tab becomes visible again.
 */
export function usePolling(fn: (signal: AbortSignal) => Promise<void> | void, intervalMs: number, enabled = true) {
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    if (!enabled) return;
    let ctrl = new AbortController();
    const run = () => {
      ctrl.abort();
      ctrl = new AbortController();
      void fnRef.current(ctrl.signal);
    };
    run();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") run();
    }, intervalMs);
    const onVisible = () => {
      if (document.visibilityState === "visible") run();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      ctrl.abort();
    };
  }, [intervalMs, enabled]);
}
