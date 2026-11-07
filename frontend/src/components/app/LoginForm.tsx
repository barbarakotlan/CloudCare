"use client";

import { ArrowRight, Eye, EyeOff, HeartPulse, LoaderCircle, Stethoscope, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useLayoutEffect, useState, type FormEvent } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { errorMessage } from "@/lib/api/client";
import type { Role } from "@/lib/api/types";
import { AUTH_PROVIDER_NAME, dashboardPathFor, login, logout } from "@/lib/auth";
import { useSession } from "@/lib/auth/useSession";

const DEMO: Record<Role, { email: string; password: string; name: string }> = {
  patient: { email: "patient@demo.com", password: "demo123", name: "Jordan Lee" },
  clinician: { email: "clinician@demo.com", password: "demo123", name: "Dr. Priya Patel" },
};

export function LoginForm() {
  const router = useRouter();
  const session = useSession();
  const [role, setRole] = useState<Role>("patient");
  const [email, setEmail] = useState(DEMO.patient.email);
  const [password, setPassword] = useState(DEMO.patient.password);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const errorId = useId();

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
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const s = await login(email, password, role);
      router.replace(dashboardPathFor(s.user.role));
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

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

      <SegmentedControl<Role>
        label="I am signing in as"
        value={role}
        onChange={switchRole}
        options={[
          { value: "patient", label: "Patient", icon: <HeartPulse className="size-4" aria-hidden="true" /> },
          { value: "clinician", label: "Doctor", icon: <Stethoscope className="size-4" aria-hidden="true" /> },
        ]}
      />

      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4" noValidate aria-describedby={error ? errorId : undefined}>
        <Field label="Email" htmlFor="login-email">
          <Input
            id="login-email"
            type="email"
            autoComplete="username"
            inputMode="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={error ? true : undefined}
          />
        </Field>
        <Field label="Password" htmlFor="login-password">
          <div className="relative">
            <Input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
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
              className="absolute top-1/2 right-2 grid size-9 -translate-y-1/2 place-items-center rounded-full text-brand-gray hover:bg-surface-pale hover:text-ink"
            >
              {showPassword ? <EyeOff className="size-5" aria-hidden="true" /> : <Eye className="size-5" aria-hidden="true" />}
            </button>
          </div>
        </Field>

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

        <Button type="submit" size="lg" className="mt-2 w-full" disabled={submitting || !email || !password}>
          {submitting ? (
            <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowRight className="size-5" aria-hidden="true" />
          )}
          {submitting ? "Signing in…" : role === "clinician" ? "Sign in to the care team view" : "Sign in to my recovery"}
        </Button>
      </form>

      <div className="mt-6 rounded-3xl border border-dashed border-line p-4 text-sm text-ink-soft">
        <p className="font-bold text-ink">Demo account</p>
        <p className="mt-1">
          {role === "clinician" ? "Doctor" : "Patient"}: <span className="font-semibold text-ink">{DEMO[role].name}</span> ·{" "}
          <code className="font-semibold text-brand-cyan-strong">{DEMO[role].email}</code> · password{" "}
          <code className="font-semibold text-brand-cyan-strong">{DEMO[role].password}</code>
        </p>
        {AUTH_PROVIDER_NAME === "supabase" ? (
          <p className="mt-2 text-xs text-brand-gray">Signing in with Supabase.</p>
        ) : null}
      </div>
    </div>
  );
}
