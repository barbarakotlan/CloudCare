"use client";

import { CheckCircle2, KeyRound, LoaderCircle, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { errorMessage } from "@/lib/api/client";
import { AUTH_PROVIDER_NAME, completePasswordReset, dashboardPathFor } from "@/lib/auth";
import { getSupabaseClient, SUPABASE_NOT_CONFIGURED } from "@/lib/supabase/client";

/** Supabase's default minimum password length (same as sign-up). */
const MIN_PASSWORD = 6;

type Phase =
  | { kind: "checking" }
  | { kind: "ready" }
  | { kind: "invalid"; message: string }
  | { kind: "saving" }
  | { kind: "done" };

const EXPIRED = "This reset link has expired or was already used. Ask for a new one from the sign-in page.";

/** Supabase reports a bad or expired link in the URL hash or query (error, error_code, error_description). */
function linkError(): string | null {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  new URLSearchParams(window.location.search).forEach((value, key) => {
    if (!params.has(key)) params.set(key, value);
  });
  const code = params.get("error_code");
  const description = params.get("error_description");
  if (!code && !params.get("error")) return null;
  if (code === "otp_expired" || /expired|invalid/i.test(description ?? "")) return EXPIRED;
  return description ?? EXPIRED;
}

/**
 * Landing page for the password reset email. The Supabase client reads the recovery
 * session from the link on load; once it exists the patient (or clinician) picks a new
 * password, is signed into CloudCare and goes to their dashboard.
 */
export function ResetPasswordForm() {
  const router = useRouter();
  const ids = useId();
  const [phase, setPhase] = useState<Phase>({ kind: "checking" });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const supabase = AUTH_PROVIDER_NAME === "supabase" ? getSupabaseClient() : null;

    const { data } = supabase?.auth.onAuthStateChange((event, session) => {
      // Keep this synchronous (see SupabaseSessionSync).
      if (!active) return;
      if (event === "PASSWORD_RECOVERY") {
        setPhase((p) => (p.kind === "checking" || p.kind === "invalid" ? { kind: "ready" } : p));
      } else if (event === "SIGNED_IN" && session) {
        setPhase((p) => (p.kind === "checking" ? { kind: "ready" } : p));
      }
    }) ?? { data: null };

    void (async () => {
      if (!supabase) {
        await Promise.resolve();
        if (active) {
          setPhase({
            kind: "invalid",
            message:
              AUTH_PROVIDER_NAME === "supabase"
                ? SUPABASE_NOT_CONFIGURED
                : "Password reset isn't available on this server. Ask your care team for help signing in.",
          });
        }
        return;
      }
      // getSession waits for the client to finish reading the link in the URL.
      const { data: current } = await supabase.auth.getSession();
      if (!active) return;
      const problem = linkError();
      if (problem) setPhase({ kind: "invalid", message: problem });
      else if (current.session) setPhase((p) => (p.kind === "checking" ? { kind: "ready" } : p));
      else setPhase({ kind: "invalid", message: EXPIRED });
    })();

    return () => {
      active = false;
      data?.subscription.unsubscribe();
    };
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (phase.kind !== "ready") return;
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(`Use a password with at least ${MIN_PASSWORD} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    setPhase({ kind: "saving" });
    try {
      const session = await completePasswordReset(password);
      setPhase({ kind: "done" });
      router.replace(dashboardPathFor(session.user.role));
    } catch (err) {
      setError(errorMessage(err));
      setPhase({ kind: "ready" });
    }
  }

  if (phase.kind === "checking") {
    return (
      <div className="mt-8" aria-busy="true">
        <p className="sr-only" role="status">
          Checking your reset link…
        </p>
        <SkeletonLines lines={3} />
      </div>
    );
  }

  if (phase.kind === "invalid") {
    return (
      <div className="mt-8 flex flex-col gap-4">
        <p
          role="alert"
          className="flex items-start gap-2 rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark ring-1 ring-brand-red/20"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {phase.message}
        </p>
        <ButtonLink href="/login" variant="secondary" className="self-start">
          Back to sign in
        </ButtonLink>
      </div>
    );
  }

  if (phase.kind === "done") {
    return (
      <p role="status" className="mt-8 flex items-center gap-2 font-bold text-[#146b49]">
        <CheckCircle2 className="size-5" aria-hidden="true" />
        Password updated. Opening your dashboard…
      </p>
    );
  }

  const saving = phase.kind === "saving";
  return (
    <form onSubmit={onSubmit} noValidate className="mt-8 flex flex-col gap-4">
      <p className="text-ink-soft">Pick a password you haven&rsquo;t used here before.</p>
      <Field label="New password" htmlFor={`${ids}-new`} hint={`At least ${MIN_PASSWORD} characters.`}>
        <Input
          id={`${ids}-new`}
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={error ? true : undefined}
          autoFocus
        />
      </Field>
      <Field label="Confirm new password" htmlFor={`${ids}-confirm`}>
        <Input
          id={`${ids}-confirm`}
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          aria-invalid={error ? true : undefined}
        />
      </Field>
      {error ? (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-2xl bg-brand-red/8 px-4 py-3 text-sm font-semibold text-brand-red-dark ring-1 ring-brand-red/20"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : null}
      <Button type="submit" size="lg" className="mt-2 w-full" disabled={saving || !password || !confirm}>
        {saving ? (
          <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />
        ) : (
          <KeyRound className="size-5" aria-hidden="true" />
        )}
        {saving ? "Saving…" : "Save new password"}
      </Button>
    </form>
  );
}
