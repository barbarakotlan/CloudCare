import { BellRing, BookOpen, CircleSlash, FlaskConical, Inbox, Phone, Send, Siren, Stethoscope, type LucideIcon } from "lucide-react";
import { useId } from "react";
import { cn } from "@/lib/cn";
import { firstName, formatMessageTime } from "@/lib/format";
import { FoggyAvatar } from "./FoggyAvatar";
import { isEmergency, type UiMessage } from "./types";

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

type ChipTone = "cyan" | "red" | "muted-red" | "gray";

const CHIP_TONE: Record<ChipTone, string> = {
  cyan: "bg-surface-pale text-brand-cyan-strong",
  red: "bg-brand-red/10 text-brand-red-dark",
  "muted-red": "bg-brand-red/6 text-brand-red-dark/85",
  gray: "bg-sev-low/12 text-[#4c5560]",
};

export function StatusChip({ tone, icon: Icon, children }: { tone: ChipTone; icon: LucideIcon; children: string }) {
  return (
    <p className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold", CHIP_TONE[tone])}>
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {children}
    </p>
  );
}

/** Shown above every emergency reply. The link only opens the dialer; it never places a call. */
export function EmergencyBanner({ className }: { className?: string }) {
  const captionId = useId();
  return (
    <div
      className={cn(
        "flex flex-col gap-2.5 rounded-2xl bg-brand-red px-4 py-3 text-white shadow-[0_8px_20px_-10px_rgb(220_56_73/0.7)]",
        className,
      )}
    >
      <p className="flex items-center gap-2 text-base font-extrabold">
        <Siren className="size-5 shrink-0" aria-hidden="true" />
        Call 911 now
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <a
          href="tel:911"
          aria-describedby={captionId}
          className="inline-flex min-h-10 items-center gap-2 rounded-full bg-white px-4 text-sm font-extrabold text-brand-red-dark transition-colors hover:bg-[#fdecee] focus-visible:outline-white"
        >
          <Phone className="size-4" aria-hidden="true" />
          Call 911
        </a>
        <span id={captionId} className="text-xs font-semibold text-white/90">
          Opens your phone&rsquo;s dialer
        </span>
      </div>
    </div>
  );
}

/** Chips under a Foggy reply: plan sources, and only actions that really happened. */
function ReplyChips({ message, transcript }: { message: UiMessage; transcript: boolean }) {
  const emergency = isEmergency(message);
  const showCitations =
    message.citations.length > 0 && (message.route === null || message.route === "ANSWER_FROM_PLAN");
  const result = message.actionResult?.status;

  return (
    <>
      {showCitations ? (
        <div className="flex flex-wrap gap-1">
          {message.citations.map((c, i) => (
            <CitationChip key={`${c.section}-${i}`} section={c.section} />
          ))}
        </div>
      ) : null}
      {transcript && emergency ? (
        <StatusChip tone="red" icon={Siren}>
          Told to call 911
        </StatusChip>
      ) : null}
      {result === "sent" ? (
        <StatusChip tone="cyan" icon={Send}>
          Message sent to your care team&rsquo;s queue
        </StatusChip>
      ) : null}
      {result === "failed" ? (
        <StatusChip tone="muted-red" icon={CircleSlash}>
          Couldn&rsquo;t send the message
        </StatusChip>
      ) : null}
      {result === "simulated" ? (
        <StatusChip tone="gray" icon={FlaskConical}>
          Demo: nothing was sent
        </StatusChip>
      ) : null}
      {message.escalated && emergency && !transcript ? (
        <StatusChip tone="red" icon={BellRing}>
          Your care team&rsquo;s queue has this alert
        </StatusChip>
      ) : null}
      {message.escalated && !emergency && !transcript && result !== "sent" ? (
        <StatusChip tone="cyan" icon={Inbox}>
          Added to your care team&rsquo;s queue
        </StatusChip>
      ) : null}
    </>
  );
}

export function MessageBubble({
  message,
  showAvatar = true,
  transcript = false,
  patientName,
}: {
  message: UiMessage;
  showAvatar?: boolean;
  /** Read-only transcript for clinicians: no 911 banner or dialer link, just a tag. */
  transcript?: boolean;
  /** Transcript only: who the patient is, so their messages are labelled by name. */
  patientName?: string;
}) {
  const mine = message.role === "patient";
  const clinician = message.role === "clinician";
  const emergency = isEmergency(message);
  const speaker = mine
    ? transcript
      ? patientName
        ? firstName(patientName)
        : "Patient"
      : "You"
    : clinician
      ? "Care team"
      : "Foggy";
  const time = message.createdAt ? formatMessageTime(message.createdAt) : null;
  // Patient chat: a quiet time beside the bubble on hover or keyboard focus.
  const hoverTime =
    !transcript && time ? (
      <time
        dateTime={message.createdAt}
        className="mb-1 shrink-0 text-[0.68rem] font-semibold whitespace-nowrap text-brand-gray opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100 motion-reduce:transition-none"
      >
        {time}
      </time>
    ) : null;

  return (
    <div className="group flex animate-bubble-in flex-col gap-2">
      {emergency && !transcript ? <EmergencyBanner className="ml-10 sm:max-w-md" /> : null}
      <div className={cn("flex items-end gap-2", mine ? "justify-end" : "justify-start")}>
        {mine ? hoverTime : null}
        {!mine && showAvatar ? (
          clinician ? (
            <span
              aria-hidden="true"
              className="grid size-8 shrink-0 place-items-center rounded-full bg-ink text-white"
            >
              <Stethoscope className="size-4" />
            </span>
          ) : (
            <FoggyAvatar decorative />
          )
        ) : !mine ? (
          <span className="size-8 shrink-0" aria-hidden="true" />
        ) : null}
        <div className={cn("flex max-w-[82%] min-w-0 flex-col gap-1.5", mine ? "items-end" : "items-start")}>
          <span className="sr-only">{speaker} said:</span>
          <div
            className={cn(
              "rounded-[1.25rem] px-4 py-2.5 text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap",
              mine && "rounded-br-md bg-brand-cyan text-white",
              !mine && !clinician && !emergency && "rounded-bl-md bg-surface-pale text-ink",
              !mine && !clinician && emergency && "rounded-bl-md bg-[#fdecee] text-ink ring-1 ring-brand-red/30",
              clinician && "rounded-bl-md bg-white text-ink ring-1 ring-line",
              message.failed && "opacity-60",
            )}
          >
            {message.content}
          </div>
          {!mine ? <ReplyChips message={message} transcript={transcript} /> : null}
          {message.failed ? <p className="text-xs font-bold text-brand-red-dark">Not sent</p> : null}
          {transcript ? (
            <p aria-hidden="true" className="px-1 text-[0.7rem] font-semibold text-brand-gray">
              {speaker}
              {time ? (
                <>
                  {" · "}
                  <time dateTime={message.createdAt}>{time}</time>
                </>
              ) : null}
            </p>
          ) : null}
        </div>
        {!mine ? hoverTime : null}
      </div>
    </div>
  );
}
