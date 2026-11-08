"use client";

import { SALES_CHAT_ENABLED, SALES_OPEN_EVENT, setHidden } from "./salesStorage";

/** Footer link that brings the sales chat back (even after "hide for 7 days") and opens it. */
export function ChatWithBarbaraLink({ className }: { className?: string }) {
  if (!SALES_CHAT_ENABLED) return null;
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      onClick={() => {
        setHidden(false);
        window.dispatchEvent(new Event(SALES_OPEN_EVENT));
      }}
      className={className}
    >
      Chat with Barbara
    </button>
  );
}
