"use client";

import { ArrowRight, ArrowUp, Building2, Minus, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError } from "@/lib/api/client";
import { sendSalesChat, submitSalesLead, type SalesTurn } from "@/lib/api/sales";
import { cn } from "@/lib/cn";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { INITIAL_ONBOARDING, OnboardingFlow, type OnboardingState } from "./OnboardingFlow";
import { BarbaraBubble, BarbaraPhoto, VisitorBubble } from "./parts";
import "./sales.css";
import { loadSessionState, newMessageId, salesSessionId, saveSessionState } from "./salesStorage";

type SalesMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Inline card under an assistant message. */
  card?: "onboard" | "thanks";
  failed?: boolean;
};

type ChatState = {
  messages: SalesMessage[];
  suggestions: string[];
  onboarding: OnboardingState;
};

const READY = "Ready to onboard";

const OPENING: SalesMessage = {
  id: "opening",
  role: "assistant",
  content:
    "Hi, I'm Barbara, co-founder at CloudCare. Well, my AI twin, the real me is usually in the clinic. Are you looking at CloudCare for your hospital?",
};

const INITIAL_STATE: ChatState = {
  messages: [OPENING],
  suggestions: ["How does it work with Epic?", "What does it cost?", READY],
  onboarding: INITIAL_ONBOARDING,
};

function isChatState(v: unknown): v is ChatState {
  if (!v || typeof v !== "object") return false;
  const s = v as Partial<ChatState>;
  return (
    Array.isArray(s.messages) &&
    s.messages.every((m) => m && typeof m.content === "string" && (m.role === "user" || m.role === "assistant")) &&
    Array.isArray(s.suggestions) &&
    !!s.onboarding &&
    typeof s.onboarding.status === "string" &&
    typeof s.onboarding.step === "number"
  );
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type SendError = { kind: "generic" | "rate"; text: string };

/**
 * The open chat with Barbara (an AI twin speaking as her). The conversation
 * lives in sessionStorage for the visit, so minimising or moving between
 * public pages keeps it.
 */
export function SalesChat({
  visible,
  onMinimise,
  onClose,
}: {
  visible: boolean;
  onMinimise: () => void;
  onClose: () => void;
}) {
  const [state, setState] = useState<ChatState>(() => loadSessionState(isChatState) ?? INITIAL_STATE);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [sendError, setSendError] = useState<SendError | null>(null);
  const [leadPending, setLeadPending] = useState(false);
  const [leadError, setLeadError] = useState<string | null>(null);
  const sessionId = useRef<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const inputId = useId();

  const { messages, suggestions, onboarding } = state;
  const onboardingOpen = onboarding.status === "active" || onboarding.status === "review";

  useEffect(() => {
    saveSessionState(state);
  }, [state]);

  // Keep the newest message in view.
  useEffect(() => {
    const el = listRef.current;
    if (el && visible) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, pending, onboarding.status, onboarding.step, visible, sendError]);

  // Move focus into the panel when it opens (onboarding inputs focus themselves). Phones get the
  // panel itself rather than the composer, so the keyboard doesn't cover the opening message.
  useEffect(() => {
    if (!visible || onboardingOpen) return;
    if (window.matchMedia("(min-width: 640px)").matches) inputRef.current?.focus({ preventScroll: true });
    else panelRef.current?.focus({ preventScroll: true });
  }, [visible, onboardingOpen]);

  // Phones get a full-screen sheet: stop the page behind it from scrolling.
  useEffect(() => {
    if (!visible) return;
    const mql = window.matchMedia("(max-width: 639px)");
    const root = document.documentElement;
    const apply = () => {
      root.style.overflow = mql.matches ? "hidden" : "";
    };
    apply();
    mql.addEventListener("change", apply);
    return () => {
      mql.removeEventListener("change", apply);
      root.style.overflow = "";
    };
  }, [visible]);

  const update = useCallback((fn: (s: ChatState) => ChatState) => setState(fn), []);

  function getSessionId(): string {
    sessionId.current ??= salesSessionId();
    return sessionId.current;
  }

  async function send(text: string) {
    const message = text.trim().slice(0, 1000);
    if (!message || pending) return;
    setSendError(null);

    if (message.toLowerCase() === READY.toLowerCase()) {
      update((s) => ({
        ...s,
        suggestions: [],
        messages: [
          ...s.messages,
          { id: newMessageId(), role: "user", content: message },
          {
            id: newMessageId(),
            role: "assistant",
            content: "Wonderful. Want me to get your hospital set up? It takes two minutes.",
            card: "onboard",
          },
        ],
      }));
      return;
    }

    const history: SalesTurn[] = messages.filter((m) => !m.failed).map((m) => ({ role: m.role, content: m.content }));
    const userMsg: SalesMessage = { id: newMessageId(), role: "user", content: message };
    update((s) => ({ ...s, suggestions: [], messages: [...s.messages, userMsg] }));
    setPending(true);
    try {
      const res = await sendSalesChat({
        session_id: getSessionId(),
        message,
        history,
        page: window.location.pathname,
      });
      update((s) => ({
        ...s,
        suggestions: (res.suggestions ?? []).slice(0, 3),
        messages: [
          ...s.messages,
          {
            id: newMessageId(),
            role: "assistant",
            content: res.reply,
            card: res.cta === "onboard" && s.onboarding.status !== "submitted" ? "onboard" : undefined,
          },
        ],
      }));
    } catch (err) {
      update((s) => ({
        ...s,
        messages: s.messages.map((m) => (m.id === userMsg.id ? { ...m, failed: true } : m)),
      }));
      setSendError(
        err instanceof ApiError && err.status === 429
          ? { kind: "rate", text: message }
          : { kind: "generic", text: message },
      );
    } finally {
      setPending(false);
    }
  }

  function retry() {
    if (!sendError) return;
    const text = sendError.text;
    update((s) => ({ ...s, messages: s.messages.filter((m) => !(m.failed && m.content === text)) }));
    setSendError(null);
    void send(text);
  }

  function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!draft.trim() || pending) return;
    const text = draft;
    setDraft("");
    void send(text);
  }

  function onComposerKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  function startOnboarding() {
    setSendError(null);
    setLeadError(null);
    update((s) => ({
      ...s,
      suggestions: [],
      onboarding: { ...s.onboarding, status: "active", step: 0, returnToReview: false, anchor: s.messages.length },
    }));
  }

  function cancelOnboarding() {
    setLeadError(null);
    update((s) => ({
      ...s,
      onboarding: { ...s.onboarding, status: "idle" },
      suggestions: ["How does it work with Epic?", "What does it cost?"],
      messages: [
        ...s.messages,
        {
          id: newMessageId(),
          role: "assistant",
          content: "No problem. I've kept your answers; pick it up again whenever you like.",
        },
      ],
    }));
  }

  async function submitLead(honeypot: string) {
    if (leadPending) return;
    const a = onboarding.answers;
    setLeadPending(true);
    setLeadError(null);
    try {
      await submitSalesLead({
        session_id: getSessionId(),
        hospital: a.hospital ?? "",
        contact_name: a.contact_name ?? "",
        role: a.role ?? "",
        work_email: a.work_email ?? "",
        phone: a.phone || undefined,
        discharges_per_month: a.discharges_per_month || undefined,
        ehr: a.ehr || undefined,
        service_lines: a.service_lines || undefined,
        timeline: a.timeline || undefined,
        notes: a.notes || undefined,
        transcript: messages.filter((m) => !m.failed).map((m) => ({ role: m.role, content: m.content })),
        website: honeypot || undefined,
        page: window.location.pathname,
      });
      const name = (a.contact_name ?? "").trim().split(/\s+/)[0] || "there";
      update((s) => ({
        ...s,
        suggestions: [],
        onboarding: { ...s.onboarding, status: "submitted" },
        messages: [
          ...s.messages,
          {
            id: newMessageId(),
            role: "assistant",
            content: `Thank you, ${name}. I've passed this to our team and someone will reach out within one business day. Want to try the live demo while you wait?`,
            card: "thanks",
          },
        ],
      }));
    } catch (err) {
      setLeadError(
        err instanceof ApiError && err.status === 429
          ? "Too many requests from this network right now. Please try again in a little while."
          : err instanceof ApiError && err.status === 422
            ? `Something in the form needs another look: ${err.message}`
            : "I couldn't send that just now. Your answers are still here; please try Submit again, or email sales@cloudcare.icu.",
      );
    } finally {
      setLeadPending(false);
    }
  }

  // Focus trap + Escape (minimise).
  function onPanelKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.stopPropagation();
      onMinimise();
      return;
    }
    if (e.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    );
    if (items.length === 0) return;
    const firstEl = items[0];
    const lastEl = items[items.length - 1];
    const active = document.activeElement;
    const outside = active === panel || !panel.contains(active);
    if (e.shiftKey && (active === firstEl || outside)) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && (active === lastEl || outside)) {
      e.preventDefault();
      firstEl.focus();
    }
  }

  const anchor = onboarding.status === "idle" ? messages.length : Math.min(onboarding.anchor, messages.length);
  const before = messages.slice(0, anchor);
  const after = messages.slice(anchor);
  const lastAssistantId = messages.findLast((m) => m.role === "assistant")?.id;

  function renderMessage(m: SalesMessage, i: number, list: SalesMessage[]) {
    if (m.role === "user") {
      return (
        <VisitorBubble
          key={m.id}
          failed={m.failed}
          after={m.failed ? <p className="text-xs font-bold text-brand-red-dark">Not sent</p> : null}
        >
          {m.content}
        </VisitorBubble>
      );
    }
    const showAvatar = list[i + 1]?.role !== "assistant";
    return (
      <div key={m.id} className="flex flex-col gap-2">
        <BarbaraBubble showAvatar={showAvatar}>{m.content}</BarbaraBubble>
        {m.card === "onboard" ? (
          <OnboardCard
            disabled={onboardingOpen || onboarding.status === "submitted"}
            done={onboarding.status === "submitted"}
            onStart={startOnboarding}
          />
        ) : null}
        {m.card === "thanks" ? (
          <div className="ml-9 flex flex-wrap gap-2">
            <Link
              href="/login"
              className="inline-flex min-h-10 items-center gap-1.5 rounded-full bg-brand-cyan px-4 text-sm font-bold text-white transition-colors hover:bg-brand-cyan-strong"
            >
              Try the live demo
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            {m.id === lastAssistantId ? (
              <button
                type="button"
                onClick={() => inputRef.current?.focus()}
                className="inline-flex min-h-10 items-center rounded-full bg-white px-4 text-sm font-bold text-ink-soft ring-1 ring-line ring-inset hover:bg-surface-soft hover:text-ink"
              >
                Keep chatting
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      hidden={!visible}
      tabIndex={-1}
      onKeyDown={onPanelKeyDown}
      className={cn(
        "fixed inset-0 z-50 flex flex-col overflow-hidden bg-white outline-none sm:inset-auto sm:right-6 sm:bottom-6 sm:h-[min(560px,calc(100dvh-3rem))] sm:w-[380px] sm:rounded-[1.75rem] sm:shadow-lift sm:ring-1 sm:ring-line",
        visible && "cc-sales-panel-in",
      )}
    >
      <header className="flex items-center gap-3 border-b border-line/70 bg-white px-4 py-3">
        <BarbaraPhoto size={40} />
        <div className="min-w-0 flex-1">
          <h2 id={titleId} className="flex items-center gap-2 text-[1rem] leading-tight font-extrabold text-ink">
            <span className="truncate">Barbara Kotlan</span>
            <span className="shrink-0 rounded-full bg-surface-soft px-2 py-0.5 text-[0.65rem] font-bold tracking-wide text-ink-soft ring-1 ring-line">
              AI twin
            </span>
          </h2>
          <p className="mt-0.5 truncate text-xs font-semibold text-brand-gray">Co-founder &middot; CloudCare</p>
        </div>
        <button
          type="button"
          onClick={onMinimise}
          aria-label="Minimise chat"
          title="Minimise"
          className="grid size-10 shrink-0 place-items-center rounded-full text-ink-soft transition-colors hover:bg-surface-pale hover:text-ink"
        >
          <Minus className="size-5" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close chat and hide it for 7 days"
          title="Close and hide for 7 days"
          className="-mr-1 grid size-10 shrink-0 place-items-center rounded-full text-ink-soft transition-colors hover:bg-surface-pale hover:text-ink"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
      </header>

      <div
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Conversation with Barbara"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-4 py-4"
      >
        {before.map((m, i) => renderMessage(m, i, before))}
        <OnboardingFlow
          state={onboarding}
          onChange={(next) => update((s) => ({ ...s, onboarding: next }))}
          onSubmit={(honeypot) => void submitLead(honeypot)}
          pending={leadPending}
          error={leadError}
        />
        {after.map((m, i) => renderMessage(m, i, after))}
        {pending ? (
          <div className="flex items-end gap-2">
            <span className="w-7 shrink-0" aria-hidden="true" />
            <TypingIndicator label="Barbara is typing" />
          </div>
        ) : null}
        {sendError ? (
          <div className="ml-9 flex flex-wrap items-center gap-2 text-sm" role="alert">
            <span className="font-semibold text-ink-soft">
              {sendError.kind === "rate" ? "Give me a few seconds." : "Sorry, that didn't reach me. Mind trying again?"}
            </span>
            <button
              type="button"
              onClick={retry}
              className="inline-flex min-h-9 items-center gap-1 rounded-full px-3 text-sm font-bold text-brand-cyan-strong ring-1 ring-brand-cyan/30 hover:bg-surface-pale"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              Retry
            </button>
          </div>
        ) : null}
      </div>

      <div className="border-t border-line/70 bg-white px-3 pt-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        {onboardingOpen ? (
          <div className="flex items-center justify-between gap-2 px-1 pb-1">
            <p className="text-xs font-semibold text-brand-gray">
              {onboarding.status === "review"
                ? "Check your answers, then Submit."
                : `Pilot request · question ${onboarding.step + 1} of 10`}
            </p>
            <button
              type="button"
              onClick={cancelOnboarding}
              disabled={leadPending}
              className="inline-flex min-h-9 items-center rounded-full px-3 text-xs font-bold text-ink-soft hover:bg-surface-pale hover:text-ink disabled:opacity-50"
            >
              Back to chat
            </button>
          </div>
        ) : (
          <>
            {suggestions.length > 0 && !pending ? (
              <div className="mb-2 flex flex-wrap gap-1.5" role="group" aria-label="Suggested replies">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void send(s)}
                    className="min-h-9 rounded-full bg-surface-pale px-3 py-1.5 text-left text-[0.82rem] font-semibold text-brand-cyan-strong transition-colors hover:bg-[#d3edf4]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : null}
            <form onSubmit={submit} className="flex items-end gap-2">
              <label htmlFor={inputId} className="sr-only">
                Message Barbara
              </label>
              <textarea
                ref={inputRef}
                id={inputId}
                rows={1}
                value={draft}
                maxLength={1000}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onComposerKey}
                placeholder="Ask about CloudCare…"
                className="max-h-28 min-h-11 flex-1 resize-none rounded-3xl border border-line bg-surface-soft px-4 py-2.5 text-base leading-snug text-ink placeholder:text-brand-gray/80 focus:border-brand-cyan focus:bg-white focus:outline-none sm:text-[0.95rem]"
              />
              <button
                type="submit"
                disabled={!draft.trim() || pending}
                aria-label="Send message"
                className="grid size-11 shrink-0 place-items-center rounded-full bg-brand-cyan text-white transition-colors hover:bg-brand-cyan-strong disabled:bg-line disabled:text-brand-gray"
              >
                <ArrowUp className="size-5" aria-hidden="true" />
              </button>
            </form>
          </>
        )}
        <p className="mt-2 text-center text-[0.68rem] leading-snug text-brand-gray">
          Automated assistant speaking for Barbara. Please don&rsquo;t share patient information.{" "}
          <Link href="/privacy" className="font-bold text-brand-cyan-strong hover:underline">
            Privacy
          </Link>
        </p>
      </div>
    </div>
  );
}

function OnboardCard({ disabled, done, onStart }: { disabled: boolean; done: boolean; onStart: () => void }) {
  return (
    <div className="ml-9 flex animate-bubble-in flex-col gap-3 rounded-[1.25rem] bg-white p-4 ring-1 ring-brand-cyan/30 shadow-soft">
      <p className="flex items-start gap-2.5 text-sm font-bold text-ink">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-pale text-brand-cyan-strong">
          <Building2 className="size-4" aria-hidden="true" />
        </span>
        Bring CloudCare to your hospital — takes about two minutes
      </p>
      <button
        type="button"
        onClick={onStart}
        disabled={disabled}
        className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-full bg-brand-cyan px-4 text-sm font-bold text-white transition-colors hover:bg-brand-cyan-strong disabled:bg-line disabled:text-brand-gray"
      >
        {done ? "Request sent" : "Start onboarding"}
        {done ? null : <ArrowRight className="size-4" aria-hidden="true" />}
      </button>
    </div>
  );
}
