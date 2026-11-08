"use client";

import {
  ArrowRight,
  Eye,
  EyeOff,
  HeartPulse,
  LoaderCircle,
  MailCheck,
  Stethoscope,
  TriangleAlert,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useLayoutEffect, useState, type FormEvent } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { errorMessage } from "@/lib/api/client";
import type { Role } from "@/lib/api/types";
import { AUTH_PROVIDER_NAME, dashboardPathFor, login, logout, requestPasswordReset, signUpPatient } from "@/lib/auth";
import { useSession } from "@/lib/auth/useSession";
import { formatAsTyped, optionalE164 } from "@/lib/phone";

const DEMO: Record<Role, { email: string; password: string; name: string }> = {
  patient: { email: "patient@demo.com", password: "demo123", name: "Jordan Lee" },
  clinician: { email: "clinician@demo.com", password: "demo123", name: "Dr. Priya Patel" },
};

/** Supabase's default minimum password length. */
const MIN_PASSWORD = 6;

type Mode = "signin" | "signup";

/** Patient self sign-up exists only with Supabase Auth; the demo backend has fixed accounts. */
const CAN_SIGN_UP = AUTH_PROVIDER_NAME === "supabase";
/** Password reset emails come from Supabase Auth too. */
const CAN_RESET = AUTH_PROVIDER_NAME === "supabase";

type ForgotState = { kind: "idle" } | { kind: "sending" } | { kind: "sent" } | { kind: "error"; message: string };

/** Inline "send me a reset link" panel. Not a <form>: it sits inside the sign-in form. */
function ForgotPassword({
  email,
  onEmail,
  state,
  onSend,
  onClose,
}: {
  email: string;
  onEmail: (value: string) => void;
  state: ForgotState;
  onSend: () => void;
  onClose: () => void;
}) {
  const id = useId();
  return (
    <div role="group" aria-labelledby={`${id}-title`} className="flex flex-col gap-3 rounded-3xl bg-surface-pale p-4">
      <p id={`${id}-title`} className="font-bold text-ink">
        Reset your password
      </p>
      {state.kind === "sent" ? (
        <p role="status" className="flex items-start gap-2 text-sm text-ink">
          <MailCheck className="mt-0.5 size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
          If that email has an account, a reset link is on its way.
        </p>
      ) : (
        <>
          <Field label="Email for the reset link" htmlFor={`${id}-email`}>
            <Input
              id={`${id}-email`}
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={(e) => onEmail(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends the link instead of submitting the sign-in form around it.
                if (e.key === "Enter") {
                  e.preventDefault();
                  onSend();
                }
              }}
              aria-invalid={state.kind === "error" ? true : undefined}
              aria-describedby={state.kind === "error" ? `${id}-err` : undefined}
              autoFocus
            />
          </Field>
          {state.kind === "error" ? (
            <p id={`${id}-err`} role="alert" className="text-sm font-semibold text-brand-red-dark">
              {state.message}
            </p>
          ) : null}
        </>
      )}
      <div className="flex flex-wrap gap-2">
        {state.kind !== "sent" ? (
          <Button size="sm" onClick={onSend} disabled={state.kind === "sending"}>
            {state.kind === "sending" ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
            {state.kind === "sending" ? "Sending…" : "Send reset link"}
          </Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={onClose}>
          {state.kind === "sent" ? "Back to sign in" : "Cancel"}
        </Button>
      </div>
    </div>
  );
}

export function LoginForm() {
  const router = useRouter();
  const session = useSession();
  const [mode, setMode] = useState<Mode>("signin");
  const [role, setRole] = useState<Role>("patient");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [email, setEmail] = useState(DEMO.patient.email);
  const [password, setPassword] = useState(DEMO.patient.password);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotState, setForgotState] = useState<ForgotState>({ kind: "idle" });
  const errorId = useId();
  const signingUp = mode === "signup";

  async function sendReset() {
    if (forgotState.kind === "sending") return;
    if (!forgotEmail.trim()) {
      setForgotState({ kind: "error", message: "Enter the email you sign in with." });
      return;
    }
    setForgotState({ kind: "sending" });
    try {
      await requestPasswordReset(forgotEmail);
      setForgotState({ kind: "sent" });
    } catch (err) {
      setForgotState({ kind: "error", message: errorMessage(err) });
    }
  }

  // Cache Components keeps this route mounted (hidden) after we navigate to a
  // dashboard; reset the submit state so coming back shows a usable form.
  useLayoutEffect(() => {
    return () => setSubmitting(false);
  }, []);

  function switchRole(next: Role) {
    setRole(next);
    setEmail(DEMO[next].email);
    setPassword(DEMO[next].password);
    setError(null);
    setNotice(null);
  }

  function switchMode(next: Mode) {
    setMode(next);
    setForgotOpen(false);
    setError(null);
    setNotice(null);
    setShowPassword(false);
    if (next === "signup") {
      setRole("patient");
      setFullName("");
      setPhone("");
      setPhoneError(null);
      setAgreed(false);
      setEmail("");
      setPassword("");
    } else {
      switchRole(role);
    }
  }

  async function onSignIn() {
    const s = await login(email, password, role);
    router.replace(dashboardPathFor(s.user.role));
  }

  async function onSignUp() {
    if (!fullName.trim()) throw new Error("Please enter your full name.");
    if (!agreed) throw new Error("Please confirm you're 18 or older and agree to the Terms.");
    const mobile = optionalE164(phone);
    if (!mobile.ok) {
      setPhoneError(mobile.error);
      throw new Error(mobile.error);
    }
    if (password.length < MIN_PASSWORD) throw new Error(`Use a password with at least ${MIN_PASSWORD} characters.`);
    const result = await signUpPatient(fullName, email, password, mobile.e164);
    if (result.session) {
      router.replace(dashboardPathFor(result.session.user.role));
      return;
    }
    // Email confirmation is on: the account exists but has no session yet.
    const createdEmail = email.trim();
    setMode("signin");
    setRole("patient");
    setEmail(createdEmail);
    setPassword("");
    setNotice(`Check ${createdEmail} for a confirmation link, then sign in here.`);
    setSubmitting(false);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      await (signingUp ? onSignUp() : onSignIn());
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  const submitDisabled = submitting || !email || !password || (signingUp && (!fullName.trim() || !agreed));
  const submitLabel = signingUp
    ? submitting
      ? "Creating your account…"
      : "Create account"
    : submitting
      ? "Signing in…"
      : "Sign in";

  return (
    <div className="mt-8">
      {session && !submitting ? (
        <div className="mb-6 flex flex-col gap-3 rounded-3xl bg-surface-pale p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-soft">
            Signed in as <span className="font-bold text-ink">{session.user.full_name}</span>
          </p>
          <div className="flex gap-2">
            <ButtonLink href={dashboardPathFor(session.user.role)} size="sm">
              Open dashboard
            </ButtonLink>
            <Button size="sm" variant="ghost" onClick={() => void logout("/login")}>
              Log out
            </Button>
          </div>
        </div>
      ) : null}

      {signingUp ? (
        <div className="rounded-3xl bg-surface-pale p-4">
          <p className="flex items-center gap-2 font-bold text-ink">
            <HeartPulse className="size-5 text-brand-cyan-strong" aria-hidden="true" />
            New patient account
          </p>
          <p className="mt-1 text-sm text-ink-soft">
            Your care team will add your procedure and care plan. Care-team accounts are set up by your clinic.
          </p>
        </div>
      ) : (
        <SegmentedControl<Role>
          label="I am signing in as"
          value={role}
          onChange={switchRole}
          options={[
            { value: "patient", label: "Patient", icon: <HeartPulse className="size-4" aria-hidden="true" /> },
            { value: "clinician", label: "Doctor", icon: <Stethoscope className="size-4" aria-hidden="true" /> },
          ]}
        />
      )}

      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate aria-describedby={error ? errorId : undefined}>
        {signingUp ? (
          <Field label="Full name" htmlFor="login-name">
            <Input
              id="login-name"
              type="text"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              aria-invalid={error && !fullName.trim() ? true : undefined}
            />
          </Field>
        ) : null}
        {signingUp ? (
          <Field
            label="Mobile number (optional)"
            htmlFor="login-phone"
            hint={
              phoneError
                ? undefined
                : "Optional, your own number only. Foggy calls or texts it only when you press Call me or Text me. Calls are automated and aren't recorded. Message and data rates may apply."
            }
          >
            <Input
              id="login-phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="(555) 123-4567"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                setPhoneError(null);
              }}
              onBlur={() => {
                setPhone((p) => formatAsTyped(p));
                const check = optionalE164(phone);
                setPhoneError(check.ok ? null : check.error);
              }}
              aria-invalid={phoneError ? true : undefined}
              aria-describedby={phoneError ? "login-phone-error" : undefined}
            />
            {phoneError ? (
              <p id="login-phone-error" className="text-sm font-semibold text-brand-red-dark">
                {phoneError}
              </p>
            ) : null}
          </Field>
        ) : null}
        <Field label="Email" htmlFor="login-email">
          <Input
            id="login-email"
            type="email"
            autoComplete={signingUp ? "email" : "username"}
            inputMode="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={error ? true : undefined}
          />
        </Field>
        <Field
          label="Password"
          htmlFor="login-password"
          hint={signingUp ? `At least ${MIN_PASSWORD} characters.` : undefined}
        >
          <div className="relative">
            <Input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete={signingUp ? "new-password" : "current-password"}
              required
              minLength={signingUp ? MIN_PASSWORD : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pr-14"
              aria-invalid={error ? true : undefined}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              className="absolute top-1/2 right-1.5 grid size-10 -translate-y-1/2 place-items-center rounded-full text-brand-gray hover:bg-surface-pale hover:text-ink"
            >
              {showPassword ? <EyeOff className="size-5" aria-hidden="true" /> : <Eye className="size-5" aria-hidden="true" />}
            </button>
          </div>
          {CAN_RESET && !signingUp && !forgotOpen ? (
            <Button
              variant="link"
              size="sm"
              className="-ml-2 self-start px-2"
              onClick={() => {
                setForgotOpen(true);
                setForgotEmail(email);
                setForgotState({ kind: "idle" });
              }}
            >
              Forgot password?
            </Button>
          ) : null}
        </Field>

        {signingUp ? (
          <label htmlFor="login-agree" className="flex cursor-pointer items-start gap-3 text-sm leading-relaxed text-ink-soft">
            <input
              id="login-agree"
              type="checkbox"
              required
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 size-5 shrink-0 cursor-pointer rounded accent-brand-cyan-strong"
            />
            <span>
              I&rsquo;m 18 or older. I agree to the{" "}
              <Link href="/terms" className="font-bold text-brand-cyan-strong underline underline-offset-2">
                Terms
              </Link>{" "}
              and have read the{" "}
              <Link href="/privacy" className="font-bold text-brand-cyan-strong underline underline-offset-2">
                Privacy Policy
              </Link>
              .
            </span>
          </label>
        ) : null}

        {CAN_RESET && !signingUp && forgotOpen ? (
          <ForgotPassword
            email={forgotEmail}
            onEmail={setForgotEmail}
            state={forgotState}
            onSend={() => void sendReset()}
            onClose={() => setForgotOpen(false)}
          />
        ) : null}

        {error ? (
          <p
            id={errorId}
            role="alert"
            className="flex items-start gap-2 rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark ring-1 ring-brand-red/20"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {error}
          </p>
        ) : null}

        {notice ? (
          <p
            role="status"
            className="flex items-start gap-2 rounded-2xl bg-surface-pale px-4 py-3 text-sm font-semibold text-ink ring-1 ring-brand-cyan/25"
          >
            <MailCheck className="mt-0.5 size-4 shrink-0 text-brand-cyan-strong" aria-hidden="true" />
            {notice}
          </p>
        ) : null}

        <Button type="submit" size="lg" className="mt-2 w-full" disabled={submitDisabled}>
          {submitting ? (
            <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />
          ) : signingUp ? (
            <UserPlus className="size-5" aria-hidden="true" />
          ) : (
            <ArrowRight className="size-5" aria-hidden="true" />
          )}
          {submitLabel}
        </Button>

        {!signingUp && role === "clinician" ? (
          <p className="text-center text-sm text-ink-soft">Care team accounts are created by your clinic.</p>
        ) : CAN_SIGN_UP ? (
          <p className="text-center text-sm text-ink-soft">
            {signingUp ? "Already have an account?" : "New patient?"}{" "}
            <Button
              variant="link"
              size="sm"
              className="px-2"
              onClick={() => switchMode(signingUp ? "signin" : "signup")}
            >
              {signingUp ? "Sign in" : "Create account"}
            </Button>
          </p>
        ) : null}
      </form>

      {signingUp ? null : (
        <div className="mt-6 rounded-3xl border border-dashed border-line p-4 text-sm text-ink-soft">
          <p className="font-bold text-ink">Demo account</p>
          <p className="mt-1">
            {role === "clinician" ? "Doctor" : "Patient"}: <span className="font-semibold text-ink">{DEMO[role].name}</span> ·{" "}
            <code className="font-semibold text-brand-cyan-strong">{DEMO[role].email}</code> · password{" "}
            <code className="font-semibold text-brand-cyan-strong">{DEMO[role].password}</code>
          </p>
          <p className="mt-2 text-xs leading-relaxed text-brand-gray">
            Shared demo account: anyone can see and reset what you enter here. Don&rsquo;t enter real health
            information.
          </p>
        </div>
      )}
    </div>
  );
}
