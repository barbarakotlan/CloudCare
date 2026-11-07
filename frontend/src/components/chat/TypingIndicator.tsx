import { cn } from "@/lib/cn";

export function TypingIndicator({ className, label = "Foggy is typing" }: { className?: string; label?: string }) {
  return (
    <div
      className={cn(
        "inline-flex animate-bubble-in items-center gap-1 rounded-[1.25rem] rounded-bl-md bg-surface-pale px-4 py-3",
        className,
      )}
    >
      <span className="sr-only">{label}</span>
      {[0, 160, 320].map((delay) => (
        <span
          key={delay}
          aria-hidden="true"
          className="size-2 animate-typing rounded-full bg-brand-cyan"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  );
}
