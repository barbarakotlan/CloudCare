"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { BrandLockup } from "@/components/brand/CloudMark";
import { Button } from "@/components/ui/Button";
import { logout, type SessionUser } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/auth/types";

function initials(name: string) {
  return name
    .replace(/^Dr\.?\s+/i, "")
    .split(/\s+/)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function AppHeader({ user, extra }: { user: SessionUser; extra?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-white/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link href="/" className="rounded-xl" aria-label="CloudCare home">
          <BrandLockup size={38} />
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          {extra}
          <div className="hidden items-center gap-2.5 sm:flex">
            <span
              aria-hidden="true"
              className="grid size-9 place-items-center rounded-full bg-surface-pale text-sm font-extrabold text-brand-cyan-strong"
            >
              {initials(user.full_name)}
            </span>
            <div className="leading-tight">
              <p className="text-sm font-bold text-ink">{user.full_name}</p>
              <p className="text-xs text-brand-gray">{user.role === "clinician" ? "Care team" : ROLE_LABEL[user.role]}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void logout("/")}>
            <LogOut className="size-4" aria-hidden="true" />
            <span className="max-sm:sr-only">Log out</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
