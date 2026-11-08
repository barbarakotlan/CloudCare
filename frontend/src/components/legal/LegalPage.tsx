import { ChevronDown, FileWarning } from "lucide-react";
import type { ReactNode } from "react";
import { Swoosh } from "@/components/brand/Swoosh";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { cn } from "@/lib/cn";

export type TocEntry = { id: string; label: string };

/** Body-text rhythm for legal copy (no typography plugin in this project). */
const PROSE = cn(
  "[&>p]:mt-4 [&>ul]:mt-4 [&>ul]:flex [&>ul]:list-disc [&>ul]:flex-col [&>ul]:gap-2 [&>ul]:pl-6",
  "[&>ul>li]:pl-1 [&>ul>li]:marker:text-brand-cyan",
  "[&_strong]:font-extrabold [&_strong]:text-ink",
  "[&_a]:font-bold [&_a]:text-brand-cyan-strong [&_a]:underline [&_a]:decoration-brand-cyan/40 [&_a]:underline-offset-2 [&_a:hover]:decoration-brand-cyan-strong",
);

/** A value that still has to be filled in before the document is final. */
export function Placeholder({ children }: { children: ReactNode }) {
  return (
    <mark className="rounded-md bg-amber-100 px-1 font-semibold text-amber-900 ring-1 ring-amber-300 [box-decoration-break:clone]">
      [{children}]
    </mark>
  );
}

/** Marks wording that still needs a lawyer's review before the document is final. */
export function CounselNote({ children }: { children: ReactNode }) {
  return (
    <p
      role="note"
      className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-[0.95rem] leading-snug text-amber-950 ring-1 ring-amber-300"
    >
      <strong className="font-extrabold text-amber-950!">For counsel review:</strong> {children}
    </p>
  );
}

export function DraftBanner() {
  return (
    <div
      role="note"
      className="flex items-start gap-3 rounded-3xl bg-amber-50 px-5 py-4 text-amber-950 ring-1 ring-amber-300 sm:items-center"
    >
      <FileWarning className="mt-0.5 size-6 shrink-0 text-amber-700 sm:mt-0" aria-hidden="true" />
      <p className="text-[0.98rem] leading-snug">
        <strong className="font-extrabold">Draft for legal review.</strong> This document has not yet been reviewed by
        legal counsel and is not final.
      </p>
    </div>
  );
}

/** Numbered section with an anchor target that clears the sticky header. */
export function LegalSection({
  id,
  number,
  title,
  children,
}: {
  id: string;
  number?: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-28 border-t border-line pt-10 first:border-t-0 first:pt-0">
      <h2 id={`${id}-title`} className="text-2xl leading-tight font-black tracking-tight text-ink sm:text-[1.7rem]">
        {number !== undefined ? <span className="mr-2 text-brand-cyan-strong">{number}.</span> : null}
        {title}
      </h2>
      <div className={PROSE}>{children}</div>
    </section>
  );
}

/** Emphasised note inside a section (emergency guidance, key limits). */
export function Callout({ tone = "info", children }: { tone?: "info" | "alert"; children: ReactNode }) {
  return (
    <div
      className={cn(
        "mt-5 rounded-2xl px-5 py-4 font-semibold",
        tone === "alert" ? "bg-[#fdecee] text-brand-red-dark ring-1 ring-brand-red/25" : "bg-surface-pale text-ink ring-1 ring-brand-cyan/20",
      )}
    >
      {children}
    </div>
  );
}

function TocList({ toc }: { toc: TocEntry[] }) {
  return (
    <ol className="mt-3 flex flex-col gap-0.5 text-[0.95rem]">
      {toc.map((t) => (
        <li key={t.id}>
          <a
            href={`#${t.id}`}
            className="block rounded-xl px-3 py-1.5 font-semibold text-ink-soft transition-colors hover:bg-surface-pale hover:text-brand-cyan-strong"
          >
            {t.label}
          </a>
        </li>
      ))}
    </ol>
  );
}

/** Shared shell for public legal pages: brand header, draft banner, contents, readable column, footer. */
export function LegalPage({
  title,
  eyebrow = "Legal",
  meta,
  toc,
  children,
}: {
  title: string;
  eyebrow?: string;
  meta?: ReactNode;
  toc?: TocEntry[];
  children: ReactNode;
}) {
  const hasToc = Boolean(toc && toc.length > 0);
  return (
    <>
      <SiteHeader />
      <main id="main" className="flex-1 bg-surface-soft">
        <div className="bg-surface-pale">
          <div className="mx-auto max-w-6xl px-4 pt-10 pb-12 sm:px-6 sm:pt-14 sm:pb-16">
            <DraftBanner />
            <p className="mt-10 text-sm font-extrabold tracking-[0.14em] text-brand-cyan-strong uppercase">{eyebrow}</p>
            <h1 className="mt-3 text-4xl leading-[1.05] font-black tracking-tight text-balance text-ink sm:text-6xl">{title}</h1>
            <Swoosh className="mt-4 h-4 w-48 sm:w-64" />
            {meta ? <div className="mt-6 flex flex-col gap-1 text-[0.98rem] text-ink-soft">{meta}</div> : null}
          </div>
        </div>

        <div
          className={cn(
            "mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14",
            hasToc && "grid gap-8 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-14",
          )}
        >
          {hasToc && toc ? (
            <>
              {/* Phones and tablets: collapsible contents above the text. */}
              <details className="group rounded-3xl bg-white p-2 ring-1 ring-line lg:hidden">
                <summary className="flex cursor-pointer list-none items-center justify-between rounded-2xl px-3 py-2.5 font-extrabold text-ink [&::-webkit-details-marker]:hidden">
                  On this page
                  <ChevronDown className="size-5 text-brand-gray transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
                <nav aria-label="On this page" className="px-1 pb-2">
                  <TocList toc={toc} />
                </nav>
              </details>
              {/* Desktop: sticky contents beside the text. */}
              <aside className="hidden lg:block">
                <nav aria-label="On this page" className="sticky top-28 rounded-3xl bg-white p-4 ring-1 ring-line">
                  <p className="px-3 pt-1 text-xs font-extrabold tracking-[0.14em] text-brand-gray uppercase">On this page</p>
                  <TocList toc={toc} />
                </nav>
              </aside>
            </>
          ) : null}

          <article className="flex max-w-[72ch] min-w-0 flex-col gap-10 rounded-[2rem] bg-white px-5 py-8 text-[1.05rem] leading-relaxed text-ink-soft shadow-soft ring-1 ring-line sm:px-10 sm:py-12">
            {children}
          </article>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
