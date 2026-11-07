/**
 * MyChart sign-in runs in a small popup so the dashboard stays put.
 *
 * Opener: MyChartCard opens a named window on click, points it at Epic's
 * authorize URL, then waits for a message (and polls /epic/status as a backup).
 * Popup: Epic sends it back to /api/auth/callback/epic, which redirects to
 * /patient/dashboard?epic=...&popup=1. If the window still has its opener, it
 * posts the result there and closes itself; otherwise the dashboard loads as a
 * normal page and tells other CloudCare tabs over a BroadcastChannel.
 */

export const EPIC_POPUP_NAME = "cloudcare-mychart";
export const EPIC_POPUP_FEATURES = "popup,width=520,height=720";
export const EPIC_MESSAGE_TYPE = "cloudcare:epic";
const CHANNEL = "cloudcare-epic";

export type EpicResult = "connected" | "error";

export type EpicPopupMessage = { type: typeof EPIC_MESSAGE_TYPE; status: EpicResult; reason: string | null };

export function isEpicPopupMessage(data: unknown): data is EpicPopupMessage {
  if (typeof data !== "object" || data === null) return false;
  const d = data as Record<string, unknown>;
  return (
    d.type === EPIC_MESSAGE_TYPE &&
    (d.status === "connected" || d.status === "error") &&
    (d.reason === null || typeof d.reason === "string")
  );
}

/** The ?epic=&reason= result on the current URL, if any. */
export function readEpicResult(search: string): EpicPopupMessage | null {
  const params = new URLSearchParams(search);
  const status = params.get("epic");
  if (status !== "connected" && status !== "error") return null;
  return { type: EPIC_MESSAGE_TYPE, status, reason: params.get("reason") };
}

/** Our own dashboard tab that opened this window, or null (no opener, closed, or another site). */
export function sameOriginOpener(): Window | null {
  try {
    const opener = window.opener as Window | null;
    if (!opener || opener.closed) return null;
    // Throws for a cross-origin opener.
    return opener.location.origin === window.location.origin ? opener : null;
  } catch {
    return null;
  }
}

/** True in a MyChart popup that came back from Epic and can hand the result to its opener. */
export function isEpicPopupReturn(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  return params.get("popup") === "1" && readEpicResult(window.location.search) !== null && sameOriginOpener() !== null;
}

/** Tell other CloudCare tabs (used when the popup lost its opener). */
export function broadcastEpicResult(message: EpicPopupMessage) {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel(CHANNEL);
  channel.postMessage(message);
  channel.close();
}

/** Listen for results from a popup, by postMessage or BroadcastChannel. Returns a cleanup function. */
export function listenForEpicResult(onResult: (message: EpicPopupMessage) => void): () => void {
  const onMessage = (event: MessageEvent) => {
    if (event.origin !== window.location.origin || !isEpicPopupMessage(event.data)) return;
    onResult(event.data);
  };
  window.addEventListener("message", onMessage);

  let channel: BroadcastChannel | null = null;
  if (typeof BroadcastChannel !== "undefined") {
    channel = new BroadcastChannel(CHANNEL);
    channel.onmessage = (event: MessageEvent) => {
      if (isEpicPopupMessage(event.data)) onResult(event.data);
    };
  }

  return () => {
    window.removeEventListener("message", onMessage);
    channel?.close();
  };
}
