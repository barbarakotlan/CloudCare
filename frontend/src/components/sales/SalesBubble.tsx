"use client";

import { MessageCircle, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type PointerEvent } from "react";
import { cn } from "@/lib/cn";
import { BarbaraPhoto } from "./parts";
import "./sales.css";
import { SalesChat } from "./SalesChat";
import { loadBubbleMemory, nextNudgeLine, SALES_CHAT_ENABLED, SALES_OPEN_EVENT, saveBubbleMemory } from "./salesStorage";

const NUDGE_AFTER_MS = 20_000;
const NUDGE_FOR_MS = 8_000;
/** Room the launcher needs at the bottom of the page, so it never covers the footer's last lines. */
const FOOTER_SPACE = { pill: "5.5rem", icon: "4.5rem" } as const;
/** Touch: holding the small icon this long shows its × instead of opening the chat. */
const LONG_PRESS_MS = 550;
const REVEAL_FOR_MS = 4_000;

/**
 *  pill  -> first view in a visit: "Ready to onboard your hospital?"
 *  open  -> the chat panel
 *  icon  -> small round photo after any close; remembered for the visit
 *  hidden-> after the icon's tiny ×; remembered for the visit, the footer link brings it back
 */
type Mode = "pill" | "open" | "icon" | "hidden";

/** Bottom-right corner, above the phone's safe area. */
const CORNER = "fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-40 sm:right-6 sm:bottom-6";

const noSubscribe = () => () => {};

/**
 * Chat bubble for the public pages. Opens a chat with Barbara (an AI twin).
 * Renders nothing on the server or when disabled with NEXT_PUBLIC_SALES_CHAT=off.
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

function initialMode(): Mode {
  const memory = loadBubbleMemory();
  return memory === "hidden" ? "hidden" : memory === "icon" ? "icon" : "pill";
}

function SalesBubbleClient() {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [everOpened, setEverOpened] = useState(false);
  const [nudge, setNudge] = useState<string | null>(null);
  const [revealHide, setRevealHide] = useState(false);
  const nudged = useRef(false);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const prevMode = useRef<Mode>(mode);
  const pressTimer = useRef<number | null>(null);
  const longPressed = useRef(false);

  const openChat = useCallback(() => {
    setNudge(null);
    nudged.current = true;
    setEverOpened(true);
    setMode("open");
    // Once the visitor has engaged, later pages show the small icon rather than the big pill.
    saveBubbleMemory("icon");
  }, []);

  const collapse = useCallback(() => {
    setNudge(null);
    nudged.current = true;
    setMode("icon");
    saveBubbleMemory("icon");
  }, []);

  function hideForVisit() {
    setRevealHide(false);
    setMode("hidden");
    saveBubbleMemory("hidden");
  }

  // Footer link (or anything else) asks to show and open the chat.
  useEffect(() => {
    window.addEventListener(SALES_OPEN_EVENT, openChat);
    return () => window.removeEventListener(SALES_OPEN_EVENT, openChat);
  }, [openChat]);

  // Proactive nudge on the big pill only: 20 s after load, or once the visitor has scrolled through "How it works".
  useEffect(() => {
    if (mode !== "pill" || nudged.current) return;
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
  }, [mode]);

  // The nudge stays for 8 s.
  useEffect(() => {
    if (!nudge) return;
    const timer = window.setTimeout(() => setNudge(null), NUDGE_FOR_MS);
    return () => window.clearTimeout(timer);
  }, [nudge]);

  // A long-press reveal of the × fades again after a few seconds.
  useEffect(() => {
    if (!revealHide) return;
    const timer = window.setTimeout(() => setRevealHide(false), REVEAL_FOR_MS);
    return () => window.clearTimeout(timer);
  }, [revealHide]);

  // Reserve room under the footer while the pill or the icon is showing.
  useEffect(() => {
    const root = document.documentElement;
    if (mode === "pill" || mode === "icon") root.style.setProperty("--sales-bubble-space", FOOTER_SPACE[mode]);
    else root.style.removeProperty("--sales-bubble-space");
    return () => {
      root.style.removeProperty("--sales-bubble-space");
    };
  }, [mode]);

  // After a close, keep keyboard focus on the launcher that replaced the chat or pill.
  useEffect(() => {
    if (prevMode.current !== mode && (mode === "icon" || mode === "pill")) {
      launcherRef.current?.focus({ preventScroll: true });
    }
    prevMode.current = mode;
  }, [mode]);

  function clearPress() {
    if (pressTimer.current !== null) window.clearTimeout(pressTimer.current);
    pressTimer.current = null;
  }

  function onIconPointerDown(e: PointerEvent<HTMLButtonElement>) {
    longPressed.current = false;
    if (e.pointerType !== "touch") return;
    clearPress();
    pressTimer.current = window.setTimeout(() => {
      longPressed.current = true;
      setRevealHide(true);
    }, LONG_PRESS_MS);
  }

  if (mode === "hidden") return null;

  return (
    <>
      {everOpened ? <SalesChat visible={mode === "open"} onClose={collapse} /> : null}

      {mode === "pill" ? (
        <div className={cn(CORNER, "flex max-w-[calc(100vw-2rem)] flex-col items-end gap-2.5")}>
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
              ref={launcherRef}
              type="button"
              onClick={openChat}
              aria-haspopup="dialog"
              className="cc-sales-arrive cc-sales-pulse relative flex items-center gap-3 rounded-full bg-white py-2 pr-5 pl-2 text-left shadow-lift ring-1 ring-line transition-shadow hover:ring-brand-cyan/60"
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
              onClick={collapse}
              aria-label="Shrink the chat bubble"
              title="Shrink"
              className="absolute -top-2 -left-2 grid size-6 place-items-center rounded-full bg-white text-ink-soft shadow-soft ring-1 ring-line transition-colors before:absolute before:-inset-2.5 before:content-[''] hover:text-ink"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
      ) : null}

      {mode === "icon" ? (
        <div className={cn(CORNER, "group")} data-reveal={revealHide || undefined}>
          <button
            ref={launcherRef}
            type="button"
            aria-label="Chat with Barbara"
            aria-haspopup="dialog"
            title="Chat with Barbara"
            onClick={() => {
              // A long-press on a phone shows the × instead of opening the chat.
              if (longPressed.current) {
                longPressed.current = false;
                return;
              }
              openChat();
            }}
            onPointerDown={onIconPointerDown}
            onPointerUp={clearPress}
            onPointerLeave={clearPress}
            onPointerCancel={clearPress}
            onContextMenu={(e) => e.preventDefault()}
            className="cc-sales-icon-in relative block size-12 rounded-full bg-white p-0.5 shadow-lift ring-2 ring-brand-cyan transition-transform duration-200 ease-out select-none [-webkit-touch-callout:none] hover:scale-[1.06] active:scale-95 motion-reduce:transition-none motion-reduce:hover:scale-100"
          >
            <BarbaraPhoto size={44} ring={false} />
            <span
              aria-hidden="true"
              className="absolute -right-1 -bottom-1 grid size-5 place-items-center rounded-full bg-brand-cyan text-white ring-2 ring-white"
            >
              <MessageCircle className="size-3" strokeWidth={2.75} />
            </span>
          </button>
          <button
            type="button"
            onClick={hideForVisit}
            aria-label="Hide the chat for this visit"
            title="Hide for this visit"
            className={cn(
              "absolute -top-1.5 -left-1.5 grid size-5 place-items-center rounded-full bg-white text-ink-soft shadow-soft ring-1 ring-line transition-opacity duration-150 before:absolute before:-inset-2 before:content-[''] hover:text-ink motion-reduce:transition-none",
              "pointer-events-none opacity-0",
              "group-hover:pointer-events-auto group-hover:opacity-100",
              "group-has-[:focus-visible]:pointer-events-auto group-has-[:focus-visible]:opacity-100",
              "group-data-[reveal]:pointer-events-auto group-data-[reveal]:opacity-100",
            )}
          >
            <X className="size-3" aria-hidden="true" strokeWidth={2.75} />
          </button>
        </div>
      ) : null}
    </>
  );
}
