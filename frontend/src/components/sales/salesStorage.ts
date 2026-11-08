/** Settings and browser storage for the sales chat bubble. Every access is guarded: storage can be blocked. */

export const SALES_CHAT_ENABLED = process.env.NEXT_PUBLIC_SALES_CHAT !== "off";

/** Fired by the footer link (and anything else) to show and open the chat. */
export const SALES_OPEN_EVENT = "cc:sales-open";

export const BARBARA_PHOTO = "/team/barbara.png";

/** Older builds hid the bubble for 7 days in localStorage; cleared on sight. */
const LEGACY_HIDDEN_KEYS = ["cc_sales_hidden", "cc_sales_hidden_at"];

/** Per-visit bubble memory (sessionStorage). */
const BUBBLE_KEY = "cc_sales_bubble";

const SESSION_ID_KEY = "cc_sales_session";
const STATE_KEY = "cc_sales_state";
const NUDGE_KEY = "cc_sales_nudge";

export const NUDGE_LINES = [
  "Running a surgical service line? I can show you where CloudCare fits.",
  "Most teams pilot with one procedure first. Want to see how?",
  "Curious how CloudCare works alongside Epic? Ask me.",
];

function local(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function session(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/**
 * How the bubble comes back on the next page view in this visit:
 *  - null: first view, the big "Ready to onboard" pill.
 *  - "icon": the visitor has opened or closed the chat; show the small round icon.
 *  - "hidden": the visitor used the tiny × on the icon; nothing until the footer link.
 */
export type BubbleMemory = "icon" | "hidden" | null;

export function loadBubbleMemory(): BubbleMemory {
  try {
    const l = local();
    for (const key of LEGACY_HIDDEN_KEYS) l?.removeItem(key);
    const v = session()?.getItem(BUBBLE_KEY);
    return v === "icon" || v === "hidden" ? v : null;
  } catch {
    return null;
  }
}

export function saveBubbleMemory(value: BubbleMemory) {
  try {
    const s = session();
    if (!s) return;
    if (value) s.setItem(BUBBLE_KEY, value);
    else s.removeItem(BUBBLE_KEY);
  } catch {
    // Storage blocked: the bubble simply starts as the pill on the next page.
  }
}

function newId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    // Older browsers / insecure origins: a random v4-shaped UUID (the API expects UUID syntax).
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = Math.floor(Math.random() * 16);
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }
}

/** One id per visit (tab session), sent with every chat turn and the pilot request. */
export function salesSessionId(): string {
  try {
    const s = session();
    const existing = s?.getItem(SESSION_ID_KEY);
    if (existing) return existing;
    const id = newId();
    s?.setItem(SESSION_ID_KEY, id);
    return id;
  } catch {
    return newId();
  }
}

export function loadSessionState<T>(isValid: (v: unknown) => v is T): T | null {
  try {
    const raw = session()?.getItem(STATE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isValid(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveSessionState(value: unknown) {
  try {
    session()?.setItem(STATE_KEY, JSON.stringify(value));
  } catch {
    // Full or blocked: the conversation just won't survive a reload.
  }
}

/** Rotates through the nudge lines across page views in one visit. */
export function nextNudgeLine(): string {
  let i = 0;
  try {
    const s = session();
    i = Number(s?.getItem(NUDGE_KEY) ?? 0) || 0;
    s?.setItem(NUDGE_KEY, String(i + 1));
  } catch {
    i = Math.floor(Math.random() * NUDGE_LINES.length);
  }
  return NUDGE_LINES[i % NUDGE_LINES.length];
}

export function newMessageId(): string {
  return newId();
}
