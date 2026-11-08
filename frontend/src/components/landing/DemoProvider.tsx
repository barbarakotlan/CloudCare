"use client";

import { AudioLines, MessageCircle } from "lucide-react";
import Link from "next/link";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { Button, type ButtonSize, type ButtonVariant } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { TalkToFoggy } from "@/components/voice/TalkToFoggy";

type DemoKind = "chat" | "voice";
type DemoContextValue = { open: (kind: DemoKind) => void };

const DemoContext = createContext<DemoContextValue | null>(null);

/** Hosts the landing-page demo chat and voice panels; buttons anywhere on the page open them. */
export function DemoProvider({ children }: { children: ReactNode }) {
  const [openKind, setOpenKind] = useState<DemoKind | null>(null);
  const close = useCallback(() => setOpenKind(null), []);
  const value = useMemo<DemoContextValue>(() => ({ open: setOpenKind }), []);

  return (
    <DemoContext.Provider value={value}>
      {children}
      <Modal
        open={openKind === "chat"}
        onClose={close}
        variant="sheet"
        title={
          <span className="flex items-center gap-2.5">
            <FoggyAvatar size={36} decorative />
            <span>
              Text Foggy
              <span className="block text-xs font-semibold text-brand-gray">Demo · Jordan&rsquo;s knee replacement plan</span>
            </span>
          </span>
        }
        bodyClassName="flex flex-col"
      >
        <ChatPanel mode="demo" className="flex-1" autoFocus />
        <DialogNote>This demo runs in your browser. Nothing you type here is sent to anyone.</DialogNote>
      </Modal>
      <Modal
        open={openKind === "voice"}
        onClose={close}
        title="Talk to Foggy"
        description="Hands-free answers from the same care plan."
      >
        <TalkToFoggy onTryText={() => setOpenKind("chat")} />
        <DialogNote>Your voice is processed by ElevenLabs to run the conversation.</DialogNote>
      </Modal>
    </DemoContext.Provider>
  );
}

/** Small print at the bottom of a demo dialog, with the Privacy Policy link. */
function DialogNote({ children }: { children: ReactNode }) {
  return (
    <p className="shrink-0 border-t border-line px-5 py-2.5 text-xs leading-relaxed text-brand-gray">
      {children}{" "}
      <Link href="/privacy" className="font-bold text-brand-cyan-strong underline-offset-2 hover:underline">
        Privacy Policy
      </Link>
    </p>
  );
}

export function DemoButton({
  kind,
  variant,
  size = "lg",
  className,
  children,
}: {
  kind: DemoKind;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children?: ReactNode;
}) {
  const ctx = useContext(DemoContext);
  if (!ctx) throw new Error("DemoButton must be inside <DemoProvider>");
  const Icon = kind === "chat" ? MessageCircle : AudioLines;
  return (
    <Button
      variant={variant ?? (kind === "chat" ? "primary" : "secondary")}
      size={size}
      className={className}
      onClick={() => ctx.open(kind)}
      aria-haspopup="dialog"
    >
      <Icon className="size-5" aria-hidden="true" />
      {children ?? (kind === "chat" ? "Try texting Foggy" : "Talk to Foggy")}
    </Button>
  );
}
