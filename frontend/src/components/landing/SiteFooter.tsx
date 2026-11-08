import Image from "next/image";
import Link from "next/link";
import { Slogan } from "@/components/brand/Wordmark";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-surface-soft">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.2fr_1fr] md:items-end">
        <div>
          <Image
            src="/brand/cloudcare-powered-by-jab.png"
            width={1933}
            height={511}
            alt="CloudCare, powered by JAB Inc"
            className="h-auto w-[240px] sm:w-[280px]"
          />
          <Slogan className="mt-4 text-base" />
          <p className="mt-4 max-w-md text-sm leading-relaxed text-ink-soft">
            Recovery support between discharge and your follow-up visit.
          </p>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-brand-gray">
            CloudCare is not a medical device and does not give medical advice. In an emergency, call 911.
          </p>
        </div>
        <div className="flex flex-col gap-5 md:items-end">
          <nav
            aria-label="Footer"
            className="-my-2 flex flex-wrap gap-x-5 text-sm font-bold text-brand-cyan-strong [&>a]:inline-flex [&>a]:min-h-10 [&>a]:items-center"
          >
            <Link href="/#how-it-works" className="hover:underline">
              How it works
            </Link>
            <Link href="/#our-promise" className="hover:underline">
              Our promise
            </Link>
            <Link href="/team" className="hover:underline">
              Team
            </Link>
            <Link href="/terms" className="hover:underline">
              Terms
            </Link>
            <Link href="/privacy" className="hover:underline">
              Privacy
            </Link>
            <Link href="/login" className="hover:underline">
              Log in
            </Link>
          </nav>
        </div>
      </div>
    </footer>
  );
}
