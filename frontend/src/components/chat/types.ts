import type { ActionResult, ChatMessageOut, ChatReply, ChatRole, ChatRoute, CheckinState } from "@/lib/api/types";

/** What the chat UI renders; built from backend messages or local demo answers. */
export type UiMessage = {
  id: string;
  role: ChatRole;
  content: string;
  citations: Array<{ section: string }>;
  answeredFromPlan: boolean | null;
  redFlag: boolean;
  /** How Foggy handled the turn; null for older backends that do not report it. */
  route: ChatRoute | null;
  /** Foggy offered to contact the care team and is waiting for a yes or no. */
  offerContact: boolean;
  /** Outcome of an action this turn (message queued, failed, or simulated in the demo). */
  actionResult: ActionResult | null;
  checkin: CheckinState | null;
  /** True only when a real escalation was created for this turn. */
  escalated: boolean;
  createdAt?: string;
  failed?: boolean;
};

/** Emergency replies get the 911 banner, whether the backend reports a route or only `red_flag`. */
export function isEmergency(m: UiMessage): boolean {
  return m.role === "assistant" && (m.route === "EMERGENCY_911" || m.redFlag);
}

/**
 * From a live `POST /chat` reply (pass `reply`) or a history item (no `reply`).
 * History has no `escalated` flag; the backend files an alert for every red-flag message.
 */
export function fromApiMessage(m: ChatMessageOut, reply?: ChatReply): UiMessage {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    citations: m.citations.map((c) => ({ section: c.section })),
    answeredFromPlan: m.answered_from_plan,
    redFlag: m.red_flag,
    route: reply?.route ?? m.route ?? null,
    offerContact: Boolean(reply?.offer_contact || reply?.pending_action),
    actionResult: reply?.action_result ?? null,
    checkin: reply?.checkin ?? null,
    escalated: reply ? reply.escalated : m.role === "assistant" && m.red_flag,
    createdAt: m.created_at,
  };
}
