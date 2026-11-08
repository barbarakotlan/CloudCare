"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

/** Neutral head-and-shoulders silhouette, shown until (or instead of) the photo. */
function PlaceholderAvatar() {
  return (
    <svg viewBox="0 0 160 160" aria-hidden="true" className="absolute inset-0 size-full">
      <circle cx="80" cy="64" r="28" fill="#B9DCE8" />
      <path d="M26 160c0-33 24-54 54-54s54 21 54 54z" fill="#B9DCE8" />
    </svg>
  );
}

/**
 * Team photo in a soft brand-tinted disc, so a transparent cut-out looks intentional.
 * If the file in public/team/ is missing, the neutral placeholder stays.
 */
export function TeamPhoto({ src, name }: { src: string; name: string }) {
  const [status, setStatus] = useState<"loading" | "loaded" | "error">("loading");
  const img = useRef<HTMLImageElement>(null);

  // The server-rendered <img> can finish (or fail) before React attaches its handlers.
  useEffect(() => {
    const el = img.current;
    if (el?.complete) setStatus(el.naturalWidth > 0 ? "loaded" : "error");
  }, []);

  return (
    <div className="relative size-36 overflow-hidden rounded-full bg-[radial-gradient(circle_at_50%_35%,#ffffff_0%,var(--surface-pale)_55%,#cfe9f2_100%)] ring-1 ring-line sm:size-40">
      {status === "loaded" ? null : (
        <>
          <PlaceholderAvatar />
          {status === "error" ? <span className="sr-only">Photo of {name} coming soon</span> : null}
        </>
      )}
      {status === "error" ? null : (
        <Image
          ref={img}
          src={src}
          alt={name}
          fill
          sizes="160px"
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("error")}
          className={cn(
            "object-cover object-[50%_20%] transition-opacity duration-300 motion-reduce:transition-none",
            status === "loaded" ? "opacity-100" : "opacity-0",
          )}
        />
      )}
    </div>
  );
}
