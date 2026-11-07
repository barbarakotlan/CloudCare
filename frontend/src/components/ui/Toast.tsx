"use client";

import { BellRing, CheckCircle2, TriangleAlert, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ToastTone = "info" | "success" | "alert";
export type ToastItem = { id: number; title: string; body?: string; tone: ToastTone };

/** Local toast state; render <ToastViewport> once per page. */
export function useToasts(timeoutMs = 6000) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) clearTimeout(timer);
    timers.current.delete(id);
  }, []);

  const push = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = nextId.current++;
      setToasts((list) => [...list.slice(-3), { ...toast, id }]);
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), timeoutMs),
      );
    },
    [dismiss, timeoutMs],
  );

  useEffect(() => {
    const map = timers.current;
    return () => {
      map.forEach((t) => clearTimeout(t));
      map.clear();
    };
  }, []);

  return { toasts, push, dismiss };
}

const toneStyles: Record<ToastTone, { ring: string; icon: ReactNode }> = {
  info: { ring: "ring-brand-cyan/30", icon: <BellRing className="size-5 text-brand-cyan-strong" aria-hidden="true" /> },
  success: { ring: "ring-ok/30", icon: <CheckCircle2 className="size-5 text-ok" aria-hidden="true" /> },
  alert: { ring: "ring-brand-red/40", icon: <TriangleAlert className="size-5 text-brand-red" aria-hidden="true" /> },
};

export function ToastViewport({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: number) => void }) {
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end sm:px-6"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={cn(
            "pointer-events-auto flex w-full max-w-sm animate-bubble-in items-start gap-3 rounded-3xl bg-white p-4 shadow-lift ring-1",
            toneStyles[t.tone].ring,
          )}
        >
          <span className="mt-0.5">{toneStyles[t.tone].icon}</span>
          <div className="min-w-0 flex-1">
            <p className="font-bold text-ink">{t.title}</p>
            {t.body ? <p className="mt-0.5 text-sm text-ink-soft">{t.body}</p> : null}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss notification"
            className="-my-1 -mr-1 grid size-10 shrink-0 place-items-center rounded-full text-brand-gray hover:bg-surface-pale"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  );
}
