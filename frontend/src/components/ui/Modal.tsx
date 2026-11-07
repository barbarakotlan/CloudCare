"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";

type ModalVariant = "center" | "sheet" | "drawer";

const variantClasses: Record<ModalVariant, string> = {
  // center and sheet share the same desktop width (36rem) so switching between
  // the "Text Foggy" and "Talk to Foggy" dialogs doesn't jump.
  center: "m-auto w-[calc(100%-2rem)] max-w-xl max-h-[calc(100dvh-2rem)] rounded-[2rem]",
  sheet:
    "mx-0 mb-0 mt-auto h-[92dvh] max-h-[92dvh] w-full max-w-none rounded-t-[2rem] sm:m-auto sm:h-[min(760px,calc(100dvh-3rem))] sm:max-h-[calc(100dvh-3rem)] sm:w-[calc(100%-2rem)] sm:max-w-xl sm:rounded-[2rem]",
  drawer: "my-0 mr-0 ml-auto h-dvh max-h-dvh w-full max-w-2xl rounded-l-[2rem] max-sm:rounded-none",
};

/**
 * Modal built on the native <dialog> element: focus is trapped and Escape
 * closes it for free. Closing is reported through `onClose`.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  variant = "center",
  className,
  bodyClassName,
  headerExtra,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  variant?: ModalVariant;
  className?: string;
  bodyClassName?: string;
  headerExtra?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descId = useId();
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    if (!dialog.open) dialog.showModal();
    document.documentElement.dataset.modalOpen = "true";
    // Closing on cleanup also covers Activity hiding the route.
    return () => {
      if (dialog.open) dialog.close();
      delete document.documentElement.dataset.modalOpen;
    };
  }, [open]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const handleClose = () => onCloseRef.current();
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, []);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onClick={(e) => {
        // Click on the backdrop (the dialog element itself, outside the panel) closes.
        if (e.target === e.currentTarget) onClose();
      }}
      className={cn(
        "overflow-hidden border-0 bg-white p-0 shadow-lift backdrop:bg-transparent open:flex open:flex-col",
        variantClasses[variant],
        className,
      )}
    >
      {open ? (
        <>
          <header className="flex items-start justify-between gap-3 border-b border-line/70 px-5 pt-5 pb-4 sm:px-6">
            <div className="min-w-0">
              <h2 id={titleId} className="text-lg leading-snug font-extrabold text-ink">
                {title}
              </h2>
              {description ? (
                <p id={descId} className="mt-0.5 text-sm text-brand-gray">
                  {description}
                </p>
              ) : null}
              {headerExtra}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="grid size-10 shrink-0 place-items-center rounded-full text-ink-soft transition-colors hover:bg-surface-pale hover:text-ink"
            >
              <X className="size-5" aria-hidden="true" />
            </button>
          </header>
          <div className={cn("min-h-0 flex-1 overflow-y-auto", bodyClassName)}>{children}</div>
        </>
      ) : null}
    </dialog>
  );
}
