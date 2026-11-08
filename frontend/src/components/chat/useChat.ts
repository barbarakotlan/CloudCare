"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getChatHistory, sendChat } from "@/lib/api/chat";
import { errorMessage } from "@/lib/api/client";
import { DEMO_WELCOME, demoTurn, INITIAL_DEMO_STATE, type DemoState } from "@/lib/demo/foggyScript";
import { fromApiMessage, type UiMessage } from "./types";

export type ChatMode = "live" | "demo";

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `local-${Date.now()}-${Math.round(Math.random() * 1e6)}`;
}

function localMessage(role: UiMessage["role"], content: string, extra: Partial<UiMessage> = {}): UiMessage {
  return {
    id: newId(),
    role,
    content,
    citations: [],
    answeredFromPlan: null,
    redFlag: false,
    route: null,
    offerContact: false,
    actionResult: null,
    checkin: null,
    escalated: false,
    createdAt: new Date().toISOString(),
    ...extra,
  };
}

const DEMO_INTRO: UiMessage = {
  ...localMessage("assistant", DEMO_WELCOME, { route: "OPERATIONAL" }),
  id: "demo-welcome",
  createdAt: undefined,
};

/**
 * Chat state for Foggy.
 * - live: loads GET /chat/history and sends via POST /chat (patient token).
 * - demo: answers locally with the demo engine, no network; contact is simulated.
 */
export function useChat(mode: ChatMode, opts: { onEscalated?: (m: UiMessage) => void } = {}) {
  const [messages, setMessages] = useState<UiMessage[]>(mode === "demo" ? [DEMO_INTRO] : []);
  const [historyLoading, setHistoryLoading] = useState(mode === "live");
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const loadedRef = useRef(false);
  const demoStateRef = useRef<DemoState>(INITIAL_DEMO_STATE);
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
      const mine = localMessage("patient", text);
      setMessages((list) => [...list, mine]);
      setPending(true);

      try {
        let reply: UiMessage;
        if (mode === "demo") {
          await new Promise((r) => setTimeout(r, 650 + Math.min(900, text.length * 12)));
          const turn = demoTurn(text, demoStateRef.current);
          demoStateRef.current = turn.state;
          const a = turn.reply;
          reply = localMessage("assistant", a.content, {
            citations: a.citations,
            answeredFromPlan: a.route === "ANSWER_FROM_PLAN",
            redFlag: a.route === "EMERGENCY_911",
            route: a.route,
            offerContact: a.offerContact,
            actionResult: a.actionResult,
            checkin: a.checkin,
          });
        } else {
          const res = await sendChat(text);
          reply = fromApiMessage(res.message, res);
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
