"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { CloudMark } from "@/components/brand/CloudMark";
import type { Role } from "@/lib/api/types";
import type { Session } from "./session";
import { useSession } from "./useSession";

/**
 * Renders children only for a signed-in user with `role`.
 * No session, or the wrong role, redirects to /login.
 */
export function RequireRole({ role, children }: { role: Role; children: (session: Session) => ReactNode }) {
  const session = useSession();
  const router = useRouter();
  const allowed = session != null && session.user.role === role;

  useEffect(() => {
    if (session === undefined) return; // still hydrating
    if (!allowed) router.replace("/login");
  }, [session, allowed, router]);

  if (!allowed) return <FullPageLoader label={session === undefined ? "Loading your space" : "Taking you to sign in"} />;
  return <>{children(session)}</>;
}

export function FullPageLoader({ label }: { label: string }) {
  return (
    <div role="status" className="grid min-h-dvh flex-1 place-items-center bg-surface-soft px-4">
      <div className="flex flex-col items-center gap-4 text-brand-gray">
        <CloudMark size={72} className="animate-pulse" />
        <p className="font-semibold">{label}…</p>
      </div>
    </div>
  );
}
