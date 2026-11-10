"use client";

import { CloudOff, MessageCircle } from "lucide-react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/Button";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { VOICE_ENABLED } from "./voiceEnabled";

export const ELEVENLABS_AGENT_ID = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID ?? "";

// The ElevenLabs SDK touches browser audio APIs, so it only loads in the browser,
// and only once the voice panel is opened.
const VoiceSession = dynamic(() => import("./VoiceSession").then((m) => m.VoiceSession), {
  ssr: false,
  loading: () => (
    <div role="status" className="flex flex-col items-center gap-3 py-12 text-brand-gray">
      <FoggyAvatar size={64} className="animate-pulse" />
      <p className="font-semibold">Getting Foggy&rsquo;s voice ready…</p>
    </div>
  ),
});

/**
 * "Talk to Foggy": in-browser voice via ElevenLabs Conversational AI.
 * With voice switched off (NEXT_PUBLIC_VOICE_ENABLED, see voiceEnabled.ts) it shows a paused
 * state and VoiceSession is never rendered, so the voice SDK never loads. Without
 * NEXT_PUBLIC_ELEVENLABS_AGENT_ID it shows a friendly not-configured state.
 */
export function TalkToFoggy({ onTryText }: { onTryText?: () => void }) {
  if (!VOICE_ENABLED) {
    return (
      <div className="flex flex-col items-center px-6 py-10 text-center">
        <span className="grid size-20 place-items-center rounded-full bg-surface-pale text-brand-cyan-strong">
          <CloudOff className="size-9" aria-hidden="true" />
        </span>
        <h3 className="mt-5 text-xl font-extrabold text-ink">Voice is paused for now</h3>
        <p className="mt-2 max-w-sm text-ink-soft">You can still text Foggy.</p>
        {onTryText ? (
          <Button className="mt-6" onClick={onTryText}>
            <MessageCircle className="size-5" aria-hidden="true" />
            Try texting Foggy instead
          </Button>
        ) : null}
      </div>
    );
  }
  if (!ELEVENLABS_AGENT_ID) {
    return (
      <div className="flex flex-col items-center px-6 py-10 text-center">
        <span className="grid size-20 place-items-center rounded-full bg-surface-pale text-brand-cyan-strong">
          <CloudOff className="size-9" aria-hidden="true" />
        </span>
        <h3 className="mt-5 text-xl font-extrabold text-ink">Voice demo not configured yet</h3>
        <p className="mt-2 max-w-sm text-ink-soft">
          Foggy&rsquo;s voice runs on ElevenLabs Conversational AI. Once an agent is connected, you&rsquo;ll be able to
          talk through your recovery questions hands-free, from the same care plan.
        </p>
        <p className="mt-3 max-w-sm rounded-2xl bg-surface-soft px-4 py-2.5 text-left text-xs text-brand-gray ring-1 ring-line">
          For the team: set <code className="font-bold text-ink">NEXT_PUBLIC_ELEVENLABS_AGENT_ID</code> in{" "}
          <code className="font-bold text-ink">frontend/.env.local</code> and restart the dev server.
        </p>
        {onTryText ? (
          <Button className="mt-6" onClick={onTryText}>
            <MessageCircle className="size-5" aria-hidden="true" />
            Try texting Foggy instead
          </Button>
        ) : null}
      </div>
    );
  }
  return <VoiceSession agentId={ELEVENLABS_AGENT_ID} />;
}
