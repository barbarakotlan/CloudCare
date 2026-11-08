"use client";

import { ArrowLeft, Check, Pencil } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import { BarbaraBubble, VisitorBubble } from "./parts";

export type OnboardingKey =
  | "hospital"
  | "contact_name"
  | "role"
  | "work_email"
  | "phone"
  | "discharges_per_month"
  | "ehr"
  | "service_lines"
  | "timeline"
  | "notes";

export type OnboardingAnswers = Partial<Record<OnboardingKey, string>>;

export type OnboardingState = {
  status: "idle" | "active" | "review" | "submitted";
  /** Index into STEPS while active. */
  step: number;
  answers: OnboardingAnswers;
  /** Editing from the review card: Next goes straight back to the review. */
  returnToReview: boolean;
  /** Messages before this index sit above the flow in the conversation. */
  anchor: number;
};

export const INITIAL_ONBOARDING: OnboardingState = {
  status: "idle",
  step: 0,
  answers: {},
  returnToReview: false,
  anchor: 0,
};

type Step = {
  key: OnboardingKey;
  question: (a: OnboardingAnswers) => string;
  label: string;
  /** Short label on the review card. */
  short: string;
  kind: "text" | "email" | "tel" | "select" | "textarea";
  options?: string[];
  placeholder?: string;
  autoComplete?: string;
  optional?: boolean;
};

function first(name: string | undefined): string {
  return (name ?? "").trim().split(/\s+/)[0] ?? "";
}

export const STEPS: Step[] = [
  {
    key: "hospital",
    question: () => "Let's do it. Which hospital or health system are you with?",
    label: "Hospital or health system",
    short: "Hospital",
    kind: "text",
    placeholder: "e.g., Riverside Medical Center",
    autoComplete: "organization",
  },
  {
    key: "contact_name",
    question: () => "And what's your name?",
    label: "Your name",
    short: "Name",
    kind: "text",
    autoComplete: "name",
  },
  {
    key: "role",
    question: (a) => (first(a.contact_name) ? `Nice to meet you, ${first(a.contact_name)}. What's your role?` : "What's your role?"),
    label: "Your role",
    short: "Role",
    kind: "text",
    placeholder: "e.g., Director of Perioperative Services",
    autoComplete: "organization-title",
  },
  {
    key: "work_email",
    question: () => "What's the best work email to reach you?",
    label: "Work email",
    short: "Work email",
    kind: "email",
    placeholder: "name@hospital.org",
    autoComplete: "email",
  },
  {
    key: "phone",
    question: () => "A phone number, in case a call is easier? This one's optional.",
    label: "Phone (optional)",
    short: "Phone",
    kind: "tel",
    placeholder: "(555) 123-4567",
    autoComplete: "tel",
    optional: true,
  },
  {
    key: "discharges_per_month",
    question: () => "Roughly how many surgical discharges do you have per month?",
    label: "Discharges per month",
    short: "Discharges / month",
    kind: "select",
    options: ["<100", "100–500", "500–2,000", "2,000+"],
  },
  {
    key: "ehr",
    question: () => "Which EHR does your hospital run?",
    label: "EHR",
    short: "EHR",
    kind: "select",
    options: ["Epic", "Oracle Health (Cerner)", "MEDITECH", "Other"],
  },
  {
    key: "service_lines",
    question: () => "Which service lines are you most interested in?",
    label: "Service lines of interest",
    short: "Service lines",
    kind: "text",
    placeholder: "e.g., orthopedics, general surgery",
  },
  {
    key: "timeline",
    question: () => "When are you hoping to get started?",
    label: "Timeline",
    short: "Timeline",
    kind: "select",
    options: ["This quarter", "Next quarter", "Exploring"],
  },
  {
    key: "notes",
    question: () => "Anything else our team should know? Optional.",
    label: "Anything else (optional)",
    short: "Notes",
    kind: "textarea",
    optional: true,
  },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function validate(step: Step, raw: string): string | null {
  const value = raw.trim();
  if (!value) return step.optional ? null : step.kind === "select" ? "Pick one to continue." : "Please fill this in.";
  if (step.kind === "email" && !EMAIL_RE.test(value)) return "That doesn't look like an email address.";
  if (step.kind === "tel" && value.replace(/\D/g, "").length < 7) return "Please enter a full phone number.";
  if (value.length > 500) return "Please keep this under 500 characters.";
  return null;
}

const fieldClass =
  "w-full rounded-2xl border border-line bg-white px-3.5 text-base text-ink placeholder:text-brand-gray/75 transition-colors focus:border-brand-cyan focus:outline-none sm:text-[0.95rem]";

/** The answer box for the current question, styled as the visitor's reply. */
function StepInput({
  step,
  index,
  initial,
  returnToReview,
  onNext,
  onBack,
}: {
  step: Step;
  index: number;
  initial: string;
  returnToReview: boolean;
  onNext: (value: string) => void;
  onBack: () => void;
}) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  const errorId = `${id}-error`;
  const ref = useRef<HTMLInputElement & HTMLSelectElement & HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);

  // Keep the whole answer box (including any error) in view inside the chat.
  useEffect(() => {
    const id = window.setTimeout(() => formRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }), 60);
    return () => window.clearTimeout(id);
  }, [error]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const problem = validate(step, value);
    setError(problem);
    if (problem) {
      ref.current?.focus({ preventScroll: true });
      return;
    }
    onNext(value.trim());
  }

  function onTextareaKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  const common = {
    id,
    ref,
    name: step.key,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error ? errorId : undefined,
    "aria-required": step.optional ? undefined : true,
  } as const;

  return (
    <form
      ref={formRef}
      onSubmit={submit}
      noValidate
      className="ml-auto flex w-[92%] animate-bubble-in flex-col gap-2 rounded-[1.25rem] rounded-br-md bg-white p-3 ring-1 ring-brand-cyan/35"
    >
      <label htmlFor={id} className="px-0.5 text-xs font-extrabold tracking-wide text-brand-cyan-strong">
        {step.label}
      </label>
      {step.kind === "select" ? (
        <select
          {...common}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className={cn(fieldClass, "h-11 pr-8")}
        >
          <option value="" disabled>
            Choose one
          </option>
          {step.options?.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : step.kind === "textarea" ? (
        <textarea
          {...common}
          rows={3}
          value={value}
          maxLength={500}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onTextareaKey}
          className={cn(fieldClass, "resize-none py-2.5 leading-snug")}
        />
      ) : (
        <input
          {...common}
          type={step.kind}
          value={value}
          maxLength={step.kind === "tel" ? 30 : 200}
          inputMode={step.kind === "tel" ? "tel" : step.kind === "email" ? "email" : undefined}
          autoComplete={step.autoComplete}
          placeholder={step.placeholder}
          onChange={(e) => setValue(e.target.value)}
          className={cn(fieldClass, "h-11")}
        />
      )}
      {error ? (
        <p id={errorId} role="alert" className="px-0.5 text-xs font-bold text-brand-red-dark">
          {error}
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        {index > 0 && !returnToReview ? (
          <button
            type="button"
            onClick={onBack}
            className="inline-flex min-h-10 items-center gap-1 rounded-full px-2.5 text-sm font-bold text-ink-soft hover:bg-surface-pale hover:text-ink"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back
          </button>
        ) : null}
        <span className="flex-1" />
        {step.optional && !returnToReview ? (
          <button
            type="button"
            onClick={() => onNext("")}
            className="inline-flex min-h-10 items-center rounded-full px-3 text-sm font-bold text-ink-soft hover:bg-surface-pale hover:text-ink"
          >
            Skip
          </button>
        ) : null}
        <button
          type="submit"
          className="inline-flex min-h-10 items-center rounded-full bg-brand-cyan px-4 text-sm font-bold text-white transition-colors hover:bg-brand-cyan-strong"
        >
          {returnToReview ? "Save" : "Next"}
        </button>
      </div>
    </form>
  );
}

/** Review card: every answer with an Edit link, the honeypot, and Submit. */
function ReviewCard({
  answers,
  pending,
  error,
  onEdit,
  onSubmit,
}: {
  answers: OnboardingAnswers;
  pending: boolean;
  error: string | null;
  onEdit: (index: number) => void;
  onSubmit: (honeypot: string) => void;
}) {
  const [website, setWebsite] = useState("");
  const headingId = useId();
  const honeypotId = useId();
  const submitRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    submitRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <form
      aria-labelledby={headingId}
      onSubmit={(e) => {
        e.preventDefault();
        if (!pending) onSubmit(website);
      }}
      className="ml-9 animate-bubble-in rounded-[1.25rem] bg-white p-4 ring-1 ring-line"
    >
      <h3 id={headingId} className="text-sm font-extrabold text-ink">
        Your pilot request
      </h3>
      <dl className="mt-2 divide-y divide-line/70 text-sm">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-start gap-2 py-1.5">
            <div className="min-w-0 flex-1">
              <dt className="text-xs font-bold text-brand-gray">{s.short}</dt>
              <dd className="break-words text-ink">{answers[s.key] || <span className="text-brand-gray">Not given</span>}</dd>
            </div>
            <button
              type="button"
              onClick={() => onEdit(i)}
              className="inline-flex min-h-9 shrink-0 items-center gap-1 rounded-full px-2.5 text-xs font-bold text-brand-cyan-strong hover:bg-surface-pale"
            >
              <Pencil className="size-3" aria-hidden="true" />
              Edit<span className="sr-only"> {s.short}</span>
            </button>
          </div>
        ))}
      </dl>
      {/* Honeypot: off-screen and skipped by keyboard and screen readers; only bots fill it. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
        <label htmlFor={honeypotId}>Website</label>
        <input
          id={honeypotId}
          name="website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
      </div>
      {error ? (
        <p role="alert" className="mt-3 rounded-xl bg-brand-red/8 px-3 py-2 text-sm font-semibold text-brand-red-dark">
          {error}
        </p>
      ) : null}
      <button
        ref={submitRef}
        type="submit"
        disabled={pending}
        aria-busy={pending || undefined}
        className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-full bg-brand-cyan px-5 text-[0.95rem] font-bold text-white shadow-[0_6px_16px_-6px_rgb(25_154_192/0.55)] transition-colors hover:bg-brand-cyan-strong disabled:opacity-60"
      >
        {pending ? "Sending…" : "Submit"}
      </button>
      <p className="mt-2 text-center text-[0.7rem] text-brand-gray">
        We use this only to contact you about a pilot. Please don&rsquo;t include patient information.
      </p>
    </form>
  );
}

/**
 * Onboarding conducted as Barbara asking one question at a time. Answered
 * questions stay in the conversation with an Edit link; the end is a review
 * card with Submit.
 */
export function OnboardingFlow({
  state,
  onChange,
  onSubmit,
  pending,
  error,
}: {
  state: OnboardingState;
  onChange: (next: OnboardingState) => void;
  onSubmit: (honeypot: string) => void;
  pending: boolean;
  error: string | null;
}) {
  const { status, step, answers, returnToReview } = state;
  if (status === "idle") return null;

  // Editing from the review keeps every other answer in view; the edited question moves to the bottom.
  const answeredCount = status === "active" && !returnToReview ? step : STEPS.length;
  // Per-answer Edit links while answering; the review card has its own.
  const editable = status === "active";

  function edit(index: number) {
    onChange({ ...state, status: "active", step: index, returnToReview: status === "review" || returnToReview });
  }

  function next(value: string) {
    const current = STEPS[step];
    const nextAnswers = { ...answers, [current.key]: value };
    if (returnToReview || step + 1 >= STEPS.length) {
      onChange({ ...state, answers: nextAnswers, status: "review", returnToReview: false });
    } else {
      onChange({ ...state, answers: nextAnswers, step: step + 1 });
    }
  }

  return (
    <>
      {STEPS.slice(0, answeredCount).map((s, i) =>
        status === "active" && returnToReview && i === step ? null : (
          <div key={s.key} className="flex flex-col gap-3">
            <BarbaraBubble>{s.question(answers)}</BarbaraBubble>
            <VisitorBubble
              after={
                editable ? (
                  <button
                    type="button"
                    onClick={() => edit(i)}
                    className="inline-flex min-h-8 items-center gap-1 rounded-full px-2 text-xs font-bold text-brand-cyan-strong hover:bg-surface-pale"
                  >
                    <Pencil className="size-3" aria-hidden="true" />
                    Edit<span className="sr-only"> {s.short}</span>
                  </button>
                ) : null
              }
            >
              {answers[s.key] || <span className="italic opacity-85">Skipped</span>}
            </VisitorBubble>
          </div>
        ),
      )}
      {status === "active" ? (
        <div className="flex flex-col gap-3">
          <BarbaraBubble>{STEPS[step].question(answers)}</BarbaraBubble>
          <StepInput
            key={`${step}-${returnToReview}`}
            step={STEPS[step]}
            index={step}
            initial={answers[STEPS[step].key] ?? ""}
            returnToReview={returnToReview}
            onNext={next}
            onBack={() => onChange({ ...state, step: Math.max(0, step - 1) })}
          />
          <p className="sr-only" aria-live="polite">
            Question {step + 1} of {STEPS.length}
          </p>
        </div>
      ) : null}
      {status === "review" ? (
        <div className="flex flex-col gap-3">
          <BarbaraBubble>Here&rsquo;s what I&rsquo;ll pass to our team. Anything to change before I send it?</BarbaraBubble>
          <ReviewCard answers={answers} pending={pending} error={error} onEdit={edit} onSubmit={onSubmit} />
        </div>
      ) : null}
      {status === "submitted" ? (
        <p className="ml-9 inline-flex items-center gap-1.5 self-start rounded-full bg-[#e3f5ec] px-3 py-1 text-xs font-bold text-[#146b49]">
          <Check className="size-3.5" aria-hidden="true" />
          Pilot request sent
        </p>
      ) : null}
    </>
  );
}
