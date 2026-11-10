"use client";

import {
  CircleCheck,
  ClipboardCheck,
  Info,
  LoaderCircle,
  MessageSquareText,
  Pencil,
  PhoneCall,
  Smartphone,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Input";
import { VOICE_ENABLED } from "@/components/voice/voiceEnabled";
import { ApiError, errorMessage } from "@/lib/api/client";
import {
  callMe,
  getMyPhone,
  getOutreachCapabilities,
  getTextStatus,
  textMe,
  updateMyPhone,
  type OutreachCapabilities,
} from "@/lib/api/outreach";
import { cn } from "@/lib/cn";
import { useAsync } from "@/lib/hooks/useAsync";
import { formatAsTyped, formatPhone, last4Of, maskedLast4, toE164 } from "@/lib/phone";

type Channel = "sms" | "call";
type ActionState =
  | { phase: "idle" }
  | { phase: "busy" }
  | { phase: "done"; tone: "ok" | "info"; title: string; body?: string }
  | { phase: "error"; title: string; body?: string };

/** Endpoints that answer like this mean the feature isn't on this server (yet). */
const UNAVAILABLE = new Set([404, 405, 501, 503]);
const FINAL_DELIVERY = new Set(["delivered", "undelivered", "failed", "read"]);
const STATUS_POLLS = 5;
const STATUS_POLL_MS = 3000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function waitSecondsFrom(message: string): number | null {
  const m = /wait (\d+) seconds?/i.exec(message);
  return m ? Number(m[1]) : null;
}

/**
 * "Test on my phone": Foggy texts or calls the patient's own number, or they check in
 * right here. Self-contained: loads the number and the server's capabilities itself and
 * shows a clean "not set up" state when the outreach endpoints aren't there.
 */
export function TestOnPhoneCard() {
  const ids = useId();
  const profile = useAsync("outreach-me", (signal) => getMyPhone(signal));
  const caps = useAsync<OutreachCapabilities | null>("outreach-capabilities", (signal) =>
    getOutreachCapabilities(signal).catch((err: unknown) => {
      if (err instanceof ApiError && UNAVAILABLE.has(err.status)) return null;
      throw err;
    }),
  );

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [savingPhone, setSavingPhone] = useState(false);

  const [text, setText] = useState<ActionState>({ phase: "idle" });
  const [call, setCall] = useState<ActionState>({ phase: "idle" });
  const [cooldownUntil, setCooldownUntil] = useState<Record<Channel, number>>({ sms: 0, call: 0 });
  const [clock, setClock] = useState(0);

  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const remaining = (channel: Channel) => Math.max(0, Math.ceil((cooldownUntil[channel] - clock) / 1000));
  const smsWait = remaining("sms");
  const callWait = remaining("call");
  const counting = smsWait > 0 || callWait > 0;

  useEffect(() => {
    if (!counting) return;
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [counting]);

  function startCooldown(channel: Channel, seconds: number) {
    const now = Date.now();
    setClock(now);
    setCooldownUntil((c) => ({ ...c, [channel]: now + seconds * 1000 }));
  }

  // ---- what we know about the number --------------------------------------------------
  const capabilities = caps.data;
  const notSetUp = capabilities === null;
  const storedPhone = profile.data?.phone ?? null; // undefined until the profile carries `phone`
  const last4 = last4Of(storedPhone) ?? capabilities?.phone_last4 ?? null;
  const hasPhone = Boolean(storedPhone) || Boolean(capabilities?.phone_on_file);
  const phoneProblem = capabilities?.reasons.phone;

  function openEditor() {
    setDraft(storedPhone ? formatPhone(storedPhone) : "");
    setPhoneError(null);
    setEditing(true);
  }

  async function savePhone(e: FormEvent) {
    e.preventDefault();
    if (savingPhone) return;
    const check = toE164(draft);
    if (!check.ok) {
      setPhoneError(check.error);
      return;
    }
    await persistPhone(check.e164);
  }

  /** Saves a checked E.164 number, or clears it with null. */
  async function persistPhone(value: string | null) {
    if (savingPhone) return;
    setSavingPhone(true);
    setPhoneError(null);
    try {
      const saved = await updateMyPhone(value);
      if (!alive.current) return;
      profile.setData((prev) => ({ ...prev, phone: saved ? (saved.phone ?? null) : value }));
      setEditing(false);
      setText({ phase: "idle" });
      setCall({ phase: "idle" });
      caps.reload();
    } catch (err) {
      if (!alive.current) return;
      if (err instanceof ApiError && (UNAVAILABLE.has(err.status) || err.status === 403)) {
        setPhoneError("Saving your number isn't available on this server yet.");
      } else {
        setPhoneError(errorMessage(err));
      }
    } finally {
      if (alive.current) setSavingPhone(false);
    }
  }

  // ---- actions -----------------------------------------------------------------------
  function checkInHere() {
    const target = document.getElementById("check-in");
    if (!target) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    target.querySelector<HTMLElement>("input, select, textarea, button")?.focus({ preventScroll: true });
  }

  function failure(err: unknown, channel: Channel): ActionState {
    if (err instanceof ApiError) {
      if (err.status === 429) {
        const wait = waitSecondsFrom(err.message);
        if (wait) startCooldown(channel, wait);
        return { phase: "error", title: "Please wait a moment", body: err.message };
      }
      if (UNAVAILABLE.has(err.status)) {
        return {
          phase: "error",
          title: channel === "sms" ? "Texting isn't set up yet" : "Calling isn't set up yet",
          body: err.message,
        };
      }
    }
    return {
      phase: "error",
      title: channel === "sms" ? "I couldn't send the text" : "I couldn't start the call",
      body: errorMessage(err),
    };
  }

  async function followDelivery(providerId: string, to: string) {
    for (let i = 0; i < STATUS_POLLS; i += 1) {
      await sleep(STATUS_POLL_MS);
      if (!alive.current) return;
      try {
        const s = await getTextStatus(providerId);
        if (!alive.current) return;
        if (s.failed) {
          setText({ phase: "error", title: `The text to ${to} wasn't delivered`, body: s.detail ?? undefined });
          return;
        }
        if (s.delivery === "delivered" || s.delivery === "read") {
          setText({ phase: "done", tone: "ok", title: `Text delivered to ${to}` });
          return;
        }
        if (FINAL_DELIVERY.has(s.delivery)) return;
      } catch {
        return; // Keep the "sent" message; checking delivery is a bonus.
      }
    }
  }

  async function onTextMe() {
    setText({ phase: "busy" });
    try {
      const res = await textMe("checkin");
      if (!alive.current) return;
      const to = maskedLast4(res.to_last4);
      startCooldown("sms", capabilities?.limits.sms_seconds ?? 60);
      if (res.status === "sent") {
        setText({ phase: "done", tone: "info", title: `Text sent to ${to}`, body: "It can take a minute to arrive." });
        if (res.provider_id) void followDelivery(res.provider_id, to);
      } else {
        setText({ phase: "error", title: "I couldn't send the text", body: res.detail ?? undefined });
      }
    } catch (err) {
      if (alive.current) setText(failure(err, "sms"));
    }
  }

  async function onCallMe() {
    setCall({ phase: "busy" });
    try {
      const res = await callMe();
      if (!alive.current) return;
      startCooldown("call", capabilities?.limits.call_seconds ?? 120);
      if (res.status === "started") {
        setCall({
          phase: "done",
          tone: "info",
          title: `Call started, your phone (${maskedLast4(res.to_last4)}) should ring shortly`,
          body: "Foggy will walk you through a short check-in.",
        });
      } else {
        setCall({ phase: "error", title: "I couldn't start the call", body: res.detail ?? undefined });
      }
    } catch (err) {
      if (alive.current) setCall(failure(err, "call"));
    }
  }

  // ---- why a button is off ------------------------------------------------------------
  function blockedReason(channel: Channel): string | null {
    if (caps.loading && capabilities === undefined) return "Checking…";
    if (caps.error) return "Couldn't check what's available.";
    if (notSetUp || !capabilities) return "Not set up on this server yet.";
    if (!capabilities[channel]) return capabilities.reasons[channel] ?? "Not set up on this server yet.";
    if (!hasPhone) return "Add your mobile number first.";
    if (phoneProblem) return phoneProblem;
    const wait = channel === "sms" ? smsWait : callWait;
    if (wait > 0) return `Available again in ${wait} s.`;
    return null;
  }

  // Texting is only offered when the server can really send texts; otherwise check-ins stay in the app.
  const showText = capabilities?.sms === true;
  const smsBlocked = blockedReason("sms");
  const callBlocked = blockedReason("call");

  return (
    <Card aria-labelledby={`${ids}-title`}>
      <CardHeader
        id={`${ids}-title`}
        icon={<Smartphone className="size-5" aria-hidden="true" />}
        title="Test on my phone"
        description={showText ? "Check in here, or have Foggy text or call you." : "Check in here, or have Foggy call you."}
      />

      {/* What each option does, before asking for a number. */}
      <p className="mb-4 text-sm leading-relaxed text-ink-soft">
        <span className="font-bold text-ink">Call me</span> places one automated call from Foggy, in a synthetic voice,
        to this number using the same care plan. Calls aren&rsquo;t recorded; a transcript is kept for up to 30 days.{" "}
        <span className="font-bold text-ink">Check in here</span> uses this screen.{" "}
        {showText ? (
          <>
            <span className="font-bold text-ink">Text me</span> sends a text with a link to your check-in.{" "}
          </>
        ) : null}
        {VOICE_ENABLED ? (
          <>
            <span className="font-bold text-ink">Talk to Foggy</span> on this page uses your browser microphone, not
            your phone.
          </>
        ) : null}
      </p>

      {/* Number on file */}
      <div className="rounded-3xl bg-surface-pale p-4">
        {editing ? (
          <form onSubmit={savePhone} noValidate className="flex flex-col gap-3">
            <Field
              label="Mobile number"
              htmlFor={`${ids}-phone`}
              hint="US numbers by default. Start with + for another country."
            >
              <Input
                id={`${ids}-phone`}
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="(555) 123-4567"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => setDraft((d) => formatAsTyped(d))}
                aria-invalid={phoneError ? true : undefined}
                aria-describedby={phoneError ? `${ids}-phone-err` : undefined}
                autoFocus
              />
            </Field>
            {phoneError ? (
              <p id={`${ids}-phone-err`} role="alert" className="text-sm font-semibold text-brand-red-dark">
                {phoneError}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" size="sm" disabled={savingPhone || !draft.trim()}>
                {savingPhone ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
                {savingPhone ? "Saving…" : "Save number"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)} disabled={savingPhone}>
                Cancel
              </Button>
              {storedPhone ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-brand-red-dark"
                  onClick={() => void persistPhone(null)}
                  disabled={savingPhone}
                >
                  Remove number
                </Button>
              ) : null}
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-bold text-ink-soft">Your mobile number</p>
              {profile.loading && caps.loading ? (
                <p className="mt-0.5 text-brand-gray">Loading…</p>
              ) : storedPhone ? (
                <p className="mt-0.5 text-lg font-extrabold text-ink">{formatPhone(storedPhone)}</p>
              ) : last4 ? (
                <p className="mt-0.5 text-lg font-extrabold text-ink">Ending in {last4}</p>
              ) : (
                <p className="mt-0.5 text-brand-gray">No number yet</p>
              )}
              {phoneProblem && hasPhone ? (
                <p className="mt-1 text-sm font-semibold text-brand-red-dark">{phoneProblem}</p>
              ) : null}
            </div>
            <Button variant="secondary" size="sm" onClick={openEditor}>
              <Pencil className="size-4" aria-hidden="true" />
              {hasPhone ? "Edit" : "Add number"}
            </Button>
          </div>
        )}
      </div>

      {notSetUp ? (
        <p className="mt-4 flex items-start gap-2 text-sm text-ink-soft">
          <Info className="mt-0.5 size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
          Calls from Foggy aren&rsquo;t set up on this server yet. You can still check in here.
        </p>
      ) : null}
      {caps.error ? (
        <p role="alert" className="mt-4 flex flex-wrap items-center gap-2 text-sm font-semibold text-brand-red-dark">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          {caps.error}
          <Button variant="ghost" size="sm" onClick={caps.reload}>
            Try again
          </Button>
        </p>
      ) : null}

      {/* Actions */}
      <div className={cn("mt-5 grid gap-3", showText ? "sm:grid-cols-3" : "sm:grid-cols-2")}>
        <ActionButton
          icon={<ClipboardCheck className="size-5" aria-hidden="true" />}
          label="Check in here"
          hint="Opens the check-in on this page."
          onClick={checkInHere}
          variant="primary"
        />
        {showText ? (
          <ActionButton
            icon={<MessageSquareText className="size-5" aria-hidden="true" />}
            label={text.phase === "busy" ? "Sending…" : "Text me"}
            busy={text.phase === "busy"}
            hint={smsBlocked ?? "A text with a link to your check-in."}
            disabled={Boolean(smsBlocked) || text.phase === "busy"}
            onClick={() => void onTextMe()}
            describedBy={`${ids}-sms-hint`}
            hintId={`${ids}-sms-hint`}
          />
        ) : null}
        <ActionButton
          icon={<PhoneCall className="size-5" aria-hidden="true" />}
          label={call.phase === "busy" ? "Calling…" : "Call me"}
          busy={call.phase === "busy"}
          hint={callBlocked ?? "Foggy calls and asks a few check-in questions."}
          disabled={Boolean(callBlocked) || call.phase === "busy"}
          onClick={() => void onCallMe()}
          describedBy={`${ids}-call-hint`}
          hintId={`${ids}-call-hint`}
        />
      </div>

      <div role="status" aria-live="polite" className="mt-4 flex flex-col gap-2 empty:hidden">
        <StatusLine state={text} />
        <StatusLine state={call} />
      </div>

      <p className="mt-4 text-xs text-brand-gray">
        {showText ? "Foggy only texts or calls the number on your account." : "Foggy only calls the number on your account."} Foggy can&rsquo;t place emergency calls: for chest pain
        or trouble breathing, call 911.
      </p>
    </Card>
  );
}

function ActionButton({
  icon,
  label,
  hint,
  onClick,
  disabled,
  busy,
  variant = "secondary",
  describedBy,
  hintId,
}: {
  icon: ReactNode;
  label: string;
  hint: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "secondary";
  describedBy?: string;
  hintId?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Button
        variant={variant}
        onClick={onClick}
        disabled={disabled}
        aria-describedby={describedBy}
        aria-busy={busy || undefined}
        className="w-full"
      >
        {busy ? <LoaderCircle className="size-5 animate-spin" aria-hidden="true" /> : icon}
        {label}
      </Button>
      <p id={hintId} className="px-1 text-xs text-brand-gray">
        {hint}
      </p>
    </div>
  );
}

function StatusLine({ state }: { state: ActionState }) {
  if (state.phase !== "done" && state.phase !== "error") return null;
  const error = state.phase === "error";
  return (
    <div
      className={cn(
        "flex animate-bubble-in items-start gap-2 rounded-2xl px-4 py-3 text-sm ring-1",
        error
          ? "bg-brand-red/8 text-brand-red-dark ring-brand-red/20"
          : state.tone === "ok"
            ? "bg-ok/8 text-[#146b49] ring-ok/25"
            : "bg-surface-pale text-ink ring-brand-cyan/25",
      )}
    >
      {error ? (
        <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      ) : (
        <CircleCheck className="mt-0.5 size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
      )}
      <p>
        <span className="font-bold">{state.title}.</span>
        {state.body ? <span className={cn("ml-1", error ? "" : "text-ink-soft")}>{state.body}</span> : null}
      </p>
    </div>
  );
}
