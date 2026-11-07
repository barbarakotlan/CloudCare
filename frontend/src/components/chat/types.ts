import type { ChatMessageOut, ChatRole } from "@/lib/api/types";

/** What the chat UI renders; built from backend messages or local demo answers. */
export type UiMessage = {
  id: string;
  role: ChatRole;
  content: string;
  citations: Array<{ section: string }>;
  answeredFromPlan: boolean | null;
  redFlag: boolean;
  /** True when this reply went to the care team (red flag or not covered by the plan). */
  escalated: boolean;
  createdAt?: string;
  failed?: boolean;
};

export function fromApiMessage(m: ChatMessageOut, escalated?: boolean): UiMessage {
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    citations: m.citations.map((c) => ({ section: c.section })),
    answeredFromPlan: m.answered_from_plan,
    redFlag: m.red_flag,
    // History does not carry `escalated`; the backend escalates exactly these cases.
    escalated: escalated ?? (m.role === "assistant" && (m.red_flag || m.answered_from_plan === false)),
    createdAt: m.created_at,
  };
}
