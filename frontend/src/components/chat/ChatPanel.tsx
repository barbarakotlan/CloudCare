"use client";

import { ArrowUp, CheckCircle2, ShieldCheck } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { cn } from "@/lib/cn";
import { CONTACT_NO, CONTACT_YES, DEMO_SUGGESTIONS } from "@/lib/demo/foggyScript";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import type { UiMessage } from "./types";
import { useChat, type ChatMode } from "./useChat";

const LIVE_SUGGESTIONS = ["When can I shower?", "Is swelling normal?", "When can I drive?", "Can I eat sushi?"];

/**
 * Foggy chat. Same component on the landing page (mode="demo", local answers)
 * and the patient dashboard (mode="live", POST /chat).
 */
export function ChatPanel({
  mode,
  className,
  onEscalated,
  autoFocus = false,
}: {
  mode: ChatMode;
  className?: string;
  onEscalated?: (m: UiMessage) => void;
  autoFocus?: boolean;
}) {
  const { messages, send, pending, historyLoading, historyError, sendError } = useChat(mode, { onEscalated });
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inputId = useId();
  const suggestions = mode === "demo" ? DEMO_SUGGESTIONS : LIVE_SUGGESTIONS;
  const patientCount = messages.filter((m) => m.role === "patient").length;
  const last = messages.at(-1);
  // Quick replies answer only the offer in the newest Foggy message.
  const showQuickReplies = !pending && last?.role === "assistant" && last.offerContact;
  const lastReply = messages.findLast((m) => m.role === "assistant");
  const checkinStep = lastReply?.checkin?.step;
  const checkinQuestion = typeof checkinStep === "number" ? checkinStep : null;
  const inCheckin = checkinQuestion !== null;

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, pending]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!draft.trim() || pending) return;
    const text = draft;
    setDraft("");
    void send(text);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-label="Conversation with Foggy"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5"
      >
        {historyLoading ? (
          <div className="flex flex-col gap-4 py-2">
            <SkeletonLines lines={2} className="w-3/4" />
            <SkeletonLines lines={2} className="ml-auto w-2/3" />
          </div>
        ) : null}
        {historyError ? (
          <p role="alert" className="rounded-2xl bg-brand-red/8 px-4 py-3 text-sm text-brand-red-dark">
            Couldn&rsquo;t load earlier messages: {historyError}
          </p>
        ) : null}
        {!historyLoading && messages.length === 0 ? (
          <div className="m-auto max-w-xs py-6 text-center text-sm text-brand-gray">
            <p className="font-bold text-ink">Ask Foggy anything about your recovery.</p>
            <p className="mt-1">Answers come only from the care plan your clinician wrote.</p>
          </div>
        ) : null}
        {messages.map((m, i) => (
          <MessageBubble key={m.id} message={m} showAvatar={messages[i + 1]?.role !== m.role || m.role === "patient"} />
        ))}
        {showQuickReplies ? (
          <div className="ml-10 flex flex-wrap gap-2" role="group" aria-label="Reply to Foggy">
            <button
              type="button"
              onClick={() => void send(CONTACT_YES)}
              className="min-h-10 rounded-full bg-brand-cyan px-4 py-2 text-sm font-bold text-white shadow-[0_6px_16px_-8px_rgb(25_154_192/0.6)] transition-colors hover:bg-brand-cyan-strong"
            >
              {CONTACT_YES}
            </button>
            <button
              type="button"
              onClick={() => void send(CONTACT_NO)}
              className="min-h-10 rounded-full bg-white px-4 py-2 text-sm font-bold text-ink-soft ring-1 ring-line ring-inset transition-colors hover:bg-surface-soft hover:text-ink"
            >
              {CONTACT_NO}
            </button>
          </div>
        ) : null}
        {pending ? (
          <div className="flex items-end gap-2">
            <span className="size-8 shrink-0" aria-hidden="true" />
            <TypingIndicator />
          </div>
        ) : null}
      </div>

      <div className="border-t border-line/70 bg-white px-3 pt-3 pb-3 sm:px-4">
        {checkinQuestion !== null ? (
          <p className="mb-2 flex items-center gap-2 text-xs font-bold text-brand-cyan-strong" aria-live="polite">
            <span className="flex gap-1" aria-hidden="true">
              {[1, 2, 3, 4].map((n) => (
                <span key={n} className={cn("size-1.5 rounded-full", n <= checkinQuestion ? "bg-brand-cyan" : "bg-line")} />
              ))}
            </span>
            Check-in &middot; question {checkinQuestion} of 4
          </p>
        ) : null}
        {checkinStep === "done" ? (
          <p className="mb-2 flex items-center gap-1.5 text-xs font-bold text-[#146b49]" aria-live="polite">
            <CheckCircle2 className="size-3.5" aria-hidden="true" />
            {mode === "demo" ? "Demo check-in finished · nothing was saved" : "Check-in saved"}
          </p>
        ) : null}
        {patientCount < 2 && !historyLoading && !inCheckin && !showQuickReplies ? (
          <div className="-mx-1 mb-2.5 flex gap-2 overflow-x-auto px-1 pb-1" aria-label="Suggested questions">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                disabled={pending}
                onClick={() => void send(s)}
                className="min-h-10 shrink-0 rounded-full bg-surface-pale px-3 py-1.5 text-sm sm:min-h-0 font-semibold text-brand-cyan-strong transition-colors hover:bg-[#d3edf4] disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        ) : null}
        {sendError ? (
          <p role="alert" className="mb-2 text-sm font-semibold text-brand-red-dark">
            {sendError}
          </p>
        ) : null}
        <form onSubmit={submit} className="flex items-end gap-2">
          <label htmlFor={inputId} className="sr-only">
            Message Foggy
          </label>
          <textarea
            ref={inputRef}
            id={inputId}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Text Foggy…"
            maxLength={2000}
            className="max-h-32 min-h-12 flex-1 resize-none rounded-3xl border border-line bg-surface-soft px-4 py-3 text-base leading-snug sm:text-[0.98rem] text-ink placeholder:text-brand-gray/80 focus:border-brand-cyan focus:bg-white focus:outline-none"
          />
          <button
            type="submit"
            disabled={!draft.trim() || pending}
            aria-label="Send message"
            className="grid size-12 shrink-0 place-items-center rounded-full bg-brand-cyan text-white shadow-[0_6px_16px_-6px_rgb(25_154_192/0.6)] transition-colors hover:bg-brand-cyan-strong disabled:bg-line disabled:text-brand-gray disabled:shadow-none"
          >
            <ArrowUp className="size-5" aria-hidden="true" />
          </button>
        </form>
        <p className="mt-2 flex items-center justify-center gap-1.5 text-center text-[0.72rem] text-brand-gray">
          <ShieldCheck className="size-3.5 shrink-0" aria-hidden="true" />
          {mode === "demo"
            ? "Demo answers from a sample care plan. Not medical advice."
            : "Foggy answers only from your care plan. In an emergency, call 911."}
        </p>
      </div>
    </div>
  );
}
