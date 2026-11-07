"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getChatHistory, sendChat } from "@/lib/api/chat";
import { errorMessage } from "@/lib/api/client";
import { answerFromPlan, DEMO_WELCOME } from "@/lib/demo/foggyScript";
import { fromApiMessage, type UiMessage } from "./types";

export type ChatMode = "live" | "demo";

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `local-${Date.now()}-${Math.round(Math.random() * 1e6)}`;
}

const DEMO_INTRO: UiMessage = {
  id: "demo-welcome",
  role: "assistant",
  content: DEMO_WELCOME,
  citations: [],
  answeredFromPlan: true,
  redFlag: false,
  escalated: false,
};

/**
 * Chat state for Foggy.
 * - live: loads GET /chat/history and sends via POST /chat (patient token).
 * - demo: answers locally from the demo care plan, no network.
 */
export function useChat(mode: ChatMode, opts: { onEscalated?: (m: UiMessage) => void } = {}) {
  const [messages, setMessages] = useState<UiMessage[]>(mode === "demo" ? [DEMO_INTRO] : []);
  const [historyLoading, setHistoryLoading] = useState(mode === "live");
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const loadedRef = useRef(false);
  const onEscalatedRef = useRef(opts.onEscalated);

  useEffect(() => {
    onEscalatedRef.current = opts.onEscalated;
  });

  useEffect(() => {
    if (mode !== "live" || loadedRef.current) return;
    const ctrl = new AbortController();
    getChatHistory(undefined, ctrl.signal).then(
      (history) => {
        loadedRef.current = true;
        setMessages((current) => [...history.map((m) => fromApiMessage(m)), ...current]);
        setHistoryLoading(false);
      },
      (err: unknown) => {
        if (ctrl.signal.aborted) return;
        setHistoryError(errorMessage(err));
        setHistoryLoading(false);
      },
    );
    return () => ctrl.abort();
  }, [mode]);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || pending) return;
      setSendError(null);
      const mine: UiMessage = {
        id: newId(),
        role: "patient",
        content: text,
        citations: [],
        answeredFromPlan: null,
        redFlag: false,
        escalated: false,
        createdAt: new Date().toISOString(),
      };
      setMessages((list) => [...list, mine]);
      setPending(true);

      try {
        let reply: UiMessage;
        if (mode === "demo") {
          await new Promise((r) => setTimeout(r, 650 + Math.min(900, text.length * 12)));
          const a = answerFromPlan(text);
          reply = {
            id: newId(),
            role: "assistant",
            content: a.content,
            citations: a.citations.map((c) => ({ section: c.section })),
            answeredFromPlan: a.answered_from_plan,
            redFlag: a.red_flag,
            escalated: a.escalated,
            createdAt: new Date().toISOString(),
          };
        } else {
          const res = await sendChat(text);
          reply = fromApiMessage(res.message, res.escalated);
        }
        setMessages((list) => [...list, reply]);
        if (reply.escalated) onEscalatedRef.current?.(reply);
      } catch (err) {
        setMessages((list) => list.map((m) => (m.id === mine.id ? { ...m, failed: true } : m)));
        setSendError(errorMessage(err));
      } finally {
        setPending(false);
      }
    },
    [mode, pending],
  );

  return { messages, send, pending, historyLoading, historyError, sendError };
}
