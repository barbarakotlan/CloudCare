/** Settings and browser storage for the sales chat bubble. Every access is guarded: storage can be blocked. */

export const SALES_CHAT_ENABLED = process.env.NEXT_PUBLIC_SALES_CHAT !== "off";

/** Fired by the footer link (and anything else) to show and open the chat. */
export const SALES_OPEN_EVENT = "cc:sales-open";

export const BARBARA_PHOTO = "/team/barbara.png";

const HIDDEN_KEY = "cc_sales_hidden";
const HIDDEN_AT_KEY = "cc_sales_hidden_at";
const HIDE_FOR_MS = 7 * 24 * 60 * 60 * 1000;

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

/** Hidden with the X: remembered for 7 days. */
export function isHidden(): boolean {
  try {
    const s = local();
    if (s?.getItem(HIDDEN_KEY) !== "1") return false;
    const at = Number(s.getItem(HIDDEN_AT_KEY));
    if (Number.isFinite(at) && at > 0 && Date.now() - at < HIDE_FOR_MS) return true;
    s.removeItem(HIDDEN_KEY);
    s.removeItem(HIDDEN_AT_KEY);
    return false;
  } catch {
    return false;
  }
}

export function setHidden(hidden: boolean) {
  try {
    const s = local();
    if (!s) return;
    if (hidden) {
      s.setItem(HIDDEN_KEY, "1");
      s.setItem(HIDDEN_AT_KEY, String(Date.now()));
    } else {
      s.removeItem(HIDDEN_KEY);
      s.removeItem(HIDDEN_AT_KEY);
    }
  } catch {
    // Storage blocked: the bubble simply shows again next visit.
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
