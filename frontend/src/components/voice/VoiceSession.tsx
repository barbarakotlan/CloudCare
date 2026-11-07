"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { Mic, MicOff, PhoneOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

type Line = { id: number; who: "you" | "foggy"; text: string };

export function VoiceSession({ agentId }: { agentId: string }) {
  return (
    <ConversationProvider>
      <VoiceSessionInner agentId={agentId} />
    </ConversationProvider>
  );
}

function VoiceSessionInner({ agentId }: { agentId: string }) {
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [requestingMic, setRequestingMic] = useState(false);
  const nextId = useRef(1);

  const conversation = useConversation({
    onMessage: (m) => {
      const id = nextId.current++;
      setLines((l) => [...l.slice(-30), { id, who: m.role === "user" ? "you" : "foggy", text: m.message }]);
    },
    onError: (message) => setError(typeof message === "string" ? message : "Voice connection error."),
  });

  const { status, isSpeaking, isMuted, setMuted, startSession, endSession } = conversation;
  const live = status === "connected" || status === "connecting";
  const statusRef = useRef(status);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  // End the call if the panel closes mid-conversation.
  useEffect(() => {
    return () => {
      if (statusRef.current === "connected" || statusRef.current === "connecting") endSession();
    };
  }, [endSession]);

  async function start() {
    setError(null);
    setRequestingMic(true);
    try {
      // Ask for the microphone only now, after the user pressed Start.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
    } catch {
      setError("Microphone access was blocked. Allow it from your browser's address bar, then press Start again.");
      setRequestingMic(false);
      return;
    }
    setRequestingMic(false);
    startSession({ agentId, connectionType: "webrtc" });
  }

  const label =
    status === "connecting" || requestingMic
      ? "Connecting…"
      : status === "connected"
        ? isSpeaking
          ? "Foggy is speaking"
          : "Listening…"
        : "Press start and ask Foggy a question out loud.";

  return (
    <div className="flex flex-col items-center px-5 py-8 text-center sm:px-6">
      <div
        className={cn(
          "relative grid size-36 place-items-center rounded-full bg-surface-pale transition-transform duration-300",
          status === "connected" && "animate-pulse-ring",
          isSpeaking && "scale-105",
        )}
      >
        <span className="absolute inset-3 rounded-full bg-white shadow-soft" aria-hidden="true" />
        <FoggyAvatar size={96} className="relative" />
      </div>

      <p role="status" aria-live="polite" className="mt-6 min-h-6 text-lg font-bold text-ink">
        {label}
      </p>
      <p className="mt-1 max-w-sm text-sm text-brand-gray">
        Foggy answers from your care plan. Your microphone is only used while a call is active.
      </p>

      {error ? (
        <p role="alert" className="mt-4 max-w-sm rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark">
          {error}
        </p>
      ) : null}

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {!live ? (
          <Button size="lg" onClick={() => void start()} disabled={requestingMic}>
            <Mic className="size-5" aria-hidden="true" />
            Start talking
          </Button>
        ) : (
          <>
            <Button variant="secondary" onClick={() => setMuted(!isMuted)} aria-pressed={isMuted}>
              {isMuted ? <MicOff className="size-5" aria-hidden="true" /> : <Mic className="size-5" aria-hidden="true" />}
              {isMuted ? "Unmute" : "Mute"}
            </Button>
            <Button variant="danger" onClick={() => endSession()}>
              <PhoneOff className="size-5" aria-hidden="true" />
              End call
            </Button>
          </>
        )}
      </div>

      {lines.length > 0 ? (
        <ol aria-label="Call transcript" className="mt-8 flex w-full max-w-md flex-col gap-2 text-left">
          {lines.map((l) => (
            <li
              key={l.id}
              className={cn(
                "max-w-[85%] rounded-[1.1rem] px-3.5 py-2 text-sm",
                l.who === "you" ? "self-end rounded-br-md bg-brand-cyan text-white" : "self-start rounded-bl-md bg-surface-pale",
              )}
            >
              <span className="sr-only">{l.who === "you" ? "You: " : "Foggy: "}</span>
              {l.text}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
