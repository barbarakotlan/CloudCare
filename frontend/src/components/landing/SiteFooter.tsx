import Image from "next/image";
import Link from "next/link";
import { Slogan } from "@/components/brand/Wordmark";

const TRACKS = ["Ethical AI Agent", "ML & Data Science", "Healthcare"];

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
          <p className="mt-4 max-w-md text-sm leading-relaxed text-brand-gray">
            CloudCare is a hackathon prototype for the &ldquo;In the Clouds&rdquo; anesthesiology challenge. It is not a
            medical device and does not give medical advice. In an emergency, call 911.
          </p>
        </div>
        <div className="flex flex-col gap-5 md:items-end">
          <div>
            <p className="text-xs font-extrabold tracking-[0.14em] text-brand-gray uppercase md:text-right">Hackathon tracks</p>
            <ul className="mt-2 flex flex-wrap gap-2 md:justify-end">
              {TRACKS.map((t) => (
                <li key={t} className="rounded-full bg-white px-3 py-1 text-sm font-bold text-ink-soft ring-1 ring-line">
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-sm font-bold text-brand-cyan-strong">
            <Link href="/#how-it-works" className="hover:underline">
              How it works
            </Link>
            <Link href="/#our-promise" className="hover:underline">
              Our promise
            </Link>
            <Link href="/terms" className="hover:underline">
              Terms
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
