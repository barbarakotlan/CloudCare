import { CloudMark } from "@/components/brand/CloudMark";
import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <main id="main" className="grid flex-1 place-items-center bg-surface-soft px-4 py-20 text-center">
      <div className="flex flex-col items-center">
        <CloudMark size={120} />
        <h1 className="mt-6 text-3xl font-black tracking-tight text-ink sm:text-4xl">This page drifted off.</h1>
        <p className="mt-3 max-w-md text-ink-soft">We couldn&rsquo;t find what you were looking for.</p>
        <ButtonLink href="/" className="mt-8">
          Back to CloudCare
        </ButtonLink>
      </div>
    </main>
  );
}
