import { CloudMark } from "@/components/brand/CloudMark";
import { cn } from "@/lib/cn";

export function FoggyAvatar({ className, size = 32 }: { className?: string; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className={cn("grid shrink-0 place-items-center rounded-full bg-white ring-1 ring-line", className)}
      style={{ width: size, height: size }}
    >
      <CloudMark size={Math.round(size * 0.68)} />
    </span>
  );
}
