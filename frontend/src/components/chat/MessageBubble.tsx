import { BookOpen, PhoneCall, Send, Stethoscope } from "lucide-react";
import { cn } from "@/lib/cn";
import { FoggyAvatar } from "./FoggyAvatar";
import type { UiMessage } from "./types";

export function CitationChip({ section, className }: { section: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-[0.7rem] font-bold text-brand-cyan-strong ring-1 ring-brand-cyan/25",
        className,
      )}
    >
      <BookOpen className="size-3" aria-hidden="true" />
      <span className="sr-only">From your care plan section: </span>
      {section}
    </span>
  );
}

export function EscalationNote({ redFlag, className }: { redFlag: boolean; className?: string }) {
  if (redFlag) {
    return (
      <p
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full bg-brand-red/10 px-2.5 py-1 text-xs font-bold text-brand-red-dark",
          className,
        )}
      >
        <PhoneCall className="size-3.5" aria-hidden="true" />
        Care team alerted · call 911 if this is an emergency
      </p>
    );
  }
  return (
    <p
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-surface-pale px-2.5 py-1 text-xs font-bold text-brand-cyan-strong",
        className,
      )}
    >
      <Send className="size-3.5" aria-hidden="true" />
      Sent to your care team
    </p>
  );
}

export function MessageBubble({ message, showAvatar = true }: { message: UiMessage; showAvatar?: boolean }) {
  const mine = message.role === "patient";
  const clinician = message.role === "clinician";

  return (
    <div className={cn("flex animate-bubble-in items-end gap-2", mine ? "justify-end" : "justify-start")}>
      {!mine && showAvatar ? (
        clinician ? (
          <span
            aria-hidden="true"
            className="grid size-8 shrink-0 place-items-center rounded-full bg-ink text-white"
          >
            <Stethoscope className="size-4" />
          </span>
        ) : (
          <FoggyAvatar />
        )
      ) : null}
      <div className={cn("flex max-w-[82%] flex-col gap-1.5", mine ? "items-end" : "items-start")}>
        <span className="sr-only">{mine ? "You said:" : clinician ? "Care team said:" : "Foggy said:"}</span>
        <div
          className={cn(
            "rounded-[1.25rem] px-4 py-2.5 text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap",
            mine && "rounded-br-md bg-brand-cyan text-white",
            !mine && !clinician && !message.redFlag && "rounded-bl-md bg-surface-pale text-ink",
            !mine && !clinician && message.redFlag && "rounded-bl-md bg-[#fdecee] text-ink ring-1 ring-brand-red/30",
            clinician && "rounded-bl-md bg-white text-ink ring-1 ring-line",
            message.failed && "opacity-60",
          )}
        >
          {message.content}
        </div>
        {message.citations.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {message.citations.map((c, i) => (
              <CitationChip key={`${c.section}-${i}`} section={c.section} />
            ))}
          </div>
        ) : null}
        {message.escalated && !mine ? <EscalationNote redFlag={message.redFlag} /> : null}
        {message.failed ? <p className="text-xs font-bold text-brand-red-dark">Not sent</p> : null}
      </div>
    </div>
  );
}
