"use client";

import { CheckCircle2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { Button } from "@/components/ui/Button";
import { epicErrorText } from "@/lib/api/epic";
import { readEpicResult, sameOriginOpener, type EpicPopupMessage } from "@/lib/epicPopup";

/**
 * Shown inside the MyChart popup after Epic sends it back: hands the result to
 * the dashboard that opened it, then closes. If the browser keeps the window
 * open, the patient sees the outcome and a way back.
 */
export function EpicPopupReturn() {
  const [result] = useState<EpicPopupMessage | null>(() =>
    typeof window === "undefined" ? null : readEpicResult(window.location.search),
  );

  useEffect(() => {
    if (!result) return;
    const opener = sameOriginOpener();
    opener?.postMessage(result, window.location.origin);
    window.close();
  }, [result]);

  const ok = result?.status === "connected";
  return (
    <main id="main" className="grid min-h-dvh flex-1 place-items-center bg-surface-soft px-4 py-10">
      <div role="status" className="flex max-w-sm flex-col items-center text-center">
        <FoggyAvatar size={72} decorative />
        <p className="mt-4 flex items-center gap-2 text-lg font-extrabold text-ink">
          {ok ? (
            <CheckCircle2 className="size-5 text-ok" aria-hidden="true" />
          ) : (
            <TriangleAlert className="size-5 text-brand-red" aria-hidden="true" />
          )}
          {ok ? "MyChart connected" : "MyChart wasn’t connected"}
        </p>
        <p className="mt-2 text-sm text-ink-soft">
          {ok ? "You can close this window and go back to CloudCare." : epicErrorText(result?.reason ?? null)}
        </p>
        <Button className="mt-5" onClick={() => window.close()}>
          Close this window
        </Button>
      </div>
    </main>
  );
}
