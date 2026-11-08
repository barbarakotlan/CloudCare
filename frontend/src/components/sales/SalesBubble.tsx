"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { cn } from "@/lib/cn";
import { BarbaraPhoto } from "./parts";
import "./sales.css";
import { SalesChat } from "./SalesChat";
import { isHidden, nextNudgeLine, SALES_CHAT_ENABLED, SALES_OPEN_EVENT, setHidden } from "./salesStorage";

const NUDGE_AFTER_MS = 20_000;
const NUDGE_FOR_MS = 8_000;
/** Room the collapsed pill needs at the bottom of the page, so it never covers the footer's last lines. */
const FOOTER_SPACE = "5.5rem";

const noSubscribe = () => () => {};

/**
 * "Ready to onboard your hospital?" bubble for the public pages. Opens a chat
 * with Barbara (an AI twin). Renders nothing on the server, when disabled with
 * NEXT_PUBLIC_SALES_CHAT=off, or while the visitor has hidden it (7 days; the
 * footer's "Chat with Barbara" link brings it back).
 */
export function SalesBubble() {
  const mounted = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  if (!SALES_CHAT_ENABLED || !mounted) return null;
  return <SalesBubbleClient />;
}

function SalesBubbleClient() {
  const [hidden, setHiddenState] = useState(isHidden);
  const [open, setOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  const [nudge, setNudge] = useState<string | null>(null);
  const nudged = useRef(false);
  const pillRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  const openChat = useCallback(() => {
    setNudge(null);
    nudged.current = true;
    setEverOpened(true);
    setOpen(true);
  }, []);

  // Footer link (or anything else) asks to show and open the chat.
  useEffect(() => {
    const onOpen = () => {
      setHidden(false);
      setHiddenState(false);
      openChat();
    };
    window.addEventListener(SALES_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(SALES_OPEN_EVENT, onOpen);
  }, [openChat]);

  // Proactive nudge: 20 s after load, or once the visitor has scrolled through "How it works".
  useEffect(() => {
    if (hidden || open || nudged.current) return;
    const show = () => {
      if (nudged.current) return;
      nudged.current = true;
      setNudge(nextNudgeLine());
    };
    const onScroll = () => {
      const section = document.getElementById("how-it-works");
      if (section && section.getBoundingClientRect().bottom < window.innerHeight) show();
    };
    const timer = window.setTimeout(show, NUDGE_AFTER_MS);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("scroll", onScroll);
    };
  }, [hidden, open]);

  // The nudge stays for 8 s.
  useEffect(() => {
    if (!nudge) return;
    const timer = window.setTimeout(() => setNudge(null), NUDGE_FOR_MS);
    return () => window.clearTimeout(timer);
  }, [nudge]);

  // Reserve room under the footer while the pill is showing.
  useEffect(() => {
    const root = document.documentElement;
    if (!hidden && !open) root.style.setProperty("--sales-bubble-space", FOOTER_SPACE);
    else root.style.removeProperty("--sales-bubble-space");
    return () => {
      root.style.removeProperty("--sales-bubble-space");
    };
  }, [hidden, open]);

  // Back to the pill: return focus to it.
  useEffect(() => {
    if (wasOpen.current && !open) pillRef.current?.focus({ preventScroll: true });
    wasOpen.current = open;
  }, [open]);

  function hide() {
    setHidden(true);
    setHiddenState(true);
    setOpen(false);
    setNudge(null);
  }

  if (hidden) return null;

  return (
    <>
      {everOpened ? <SalesChat visible={open} onMinimise={() => setOpen(false)} onClose={hide} /> : null}
      {open ? null : (
        <div className="fixed right-4 bottom-4 z-40 flex max-w-[calc(100vw-2rem)] flex-col items-end gap-2.5 sm:right-6 sm:bottom-6">
          {nudge ? (
            <button
              type="button"
              onClick={openChat}
              className={cn(
                "relative mr-1 max-w-[17rem] rounded-2xl bg-white px-4 py-3 text-left text-sm leading-snug font-semibold text-ink shadow-lift ring-1 ring-line transition-colors hover:ring-brand-cyan/50",
                "cc-sales-nudge-in",
              )}
            >
              {nudge}
              <span
                aria-hidden="true"
                className="absolute right-9 -bottom-[7px] size-3.5 rotate-45 border-r border-b border-line bg-white"
              />
            </button>
          ) : null}
          <div className="relative">
            <button
              ref={pillRef}
              type="button"
              onClick={openChat}
              aria-haspopup="dialog"
              className={cn(
                "relative flex items-center gap-3 rounded-full bg-white py-2 pr-5 pl-2 text-left shadow-lift ring-1 ring-line transition-shadow hover:ring-brand-cyan/60",
                // The arrival bounce plays once per page view, not again after minimising.
                !everOpened && "cc-sales-arrive",
                "cc-sales-pulse",
              )}
            >
              <BarbaraPhoto size={40} />
              <span className="flex min-w-0 flex-col leading-tight">
                <span className="text-[0.95rem] font-extrabold text-ink">
                  <span className="sm:hidden">Onboard your hospital</span>
                  <span className="hidden sm:inline">Ready to onboard your hospital?</span>
                </span>
                <span className="sr-only text-xs font-semibold text-brand-gray sm:not-sr-only sm:mt-0.5">
                  Chat with Barbara, co-founder
                </span>
              </span>
            </button>
            <button
              type="button"
              onClick={hide}
              aria-label="Hide the chat bubble for 7 days"
              title="Hide for 7 days"
              className="absolute -top-2 -left-2 grid size-6 place-items-center rounded-full bg-white text-ink-soft shadow-soft ring-1 ring-line transition-colors before:absolute before:-inset-2.5 before:content-[''] hover:text-ink"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
