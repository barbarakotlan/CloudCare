import Link from "next/link";
import { BrandLockup } from "@/components/brand/CloudMark";
import { ButtonLink } from "@/components/ui/Button";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-transparent bg-white/85 backdrop-blur-md supports-[backdrop-filter]:bg-white/70">
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:h-[4.5rem] sm:px-6">
        <Link href="/" className="rounded-xl" aria-label="CloudCare home">
          <BrandLockup size={44} />
        </Link>
        <div className="flex items-center gap-1 sm:gap-2">
          <a
            href="#how-it-works"
            className="hidden rounded-full px-4 py-2 text-[0.95rem] font-bold text-ink-soft transition-colors hover:bg-surface-pale hover:text-ink md:inline-flex"
          >
            How it works
          </a>
          <a
            href="#our-promise"
            className="hidden rounded-full px-4 py-2 text-[0.95rem] font-bold text-ink-soft transition-colors hover:bg-surface-pale hover:text-ink md:inline-flex"
          >
            Our promise
          </a>
          <ButtonLink href="/login" variant="secondary" size="sm" className="h-10 px-5">
            Log in
          </ButtonLink>
        </div>
      </nav>
    </header>
  );
}
