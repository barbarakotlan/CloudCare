"use client";

import { saveBubbleMemory, SALES_CHAT_ENABLED, SALES_OPEN_EVENT } from "./salesStorage";

/** Footer link that brings the sales chat back (even after the visitor hid it) and opens it. */
export function ChatWithBarbaraLink({ className }: { className?: string }) {
  if (!SALES_CHAT_ENABLED) return null;
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      onClick={() => {
        saveBubbleMemory("icon");
        window.dispatchEvent(new Event(SALES_OPEN_EVENT));
      }}
      className={className}
    >
      Chat with Barbara
    </button>
  );
}
