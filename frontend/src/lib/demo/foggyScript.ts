import { DEMO_CARE_PLAN_CHUNKS, type DemoChunk } from "./demoCarePlan";

// ---------------------------------------------------------------------------
// 1. Scripted conversation for the landing-page phone (auto-advances, loops)
// ---------------------------------------------------------------------------

export type ScriptStep = {
  from: "foggy" | "patient";
  text: string;
  /** Care-plan section chip under a Foggy reply. */
  cite?: string;
  /** Small status line under the bubble. */
  status?: { tone: "care-team" | "logged"; text: string };
  /** How long the typing indicator shows before this message (ms). */
  typingMs: number;
};

export const LANDING_SCRIPT: ScriptStep[] = [
  {
    from: "foggy",
    text: "Morning, Jordan! Day 3 after your knee surgery. How’s your pain, 0 to 10?",
    typingMs: 1100,
  },
  { from: "patient", text: "Around a 4. Is it ok to shower today?", typingMs: 900 },
  {
    from: "foggy",
    text: "Yes. Your plan says you can shower 48 hours after surgery with the waterproof dressing on. No baths, pools or hot tubs for 4 weeks.",
    cite: "Wound care",
    status: { tone: "logged", text: "Pain 4/10 logged" },
    typingMs: 1600,
  },
  { from: "patient", text: "Can I take ibuprofen too?", typingMs: 900 },
  {
    from: "foggy",
    text: "That isn’t in your care plan, so I won’t guess. I’ve asked Dr. Patel’s team and they’ll text you back.",
    status: { tone: "care-team", text: "Sent to your care team" },
    typingMs: 1500,
  },
  { from: "patient", text: "Thank you, Foggy!", typingMs: 900 },
];

// ---------------------------------------------------------------------------
// 2. Local answers for the "Try texting Foggy" demo (no login, no network).
//    Mirrors the placeholder in backend/app/services/ai_service.py.
// ---------------------------------------------------------------------------

export const RED_FLAGS = [
  "chest pain",
  "can't breathe",
  "cannot breathe",
  "trouble breathing",
  "shortness of breath",
  "heavy bleeding",
  "bleeding a lot",
  "fainted",
  "passed out",
  "unconscious",
  "suicidal",
];

export const EMERGENCY_REPLY =
  "What you're describing can be an emergency. Please call 911 now. I've also alerted your care team.";

export const NOT_IN_PLAN_REPLY =
  "I don't see that in your care plan, so I don't want to guess. I've sent your question to your care team, and they'll get back to you.";

export type DemoAnswer = {
  content: string;
  citations: Array<{ chunk_id: string; section: string }>;
  answered_from_plan: boolean;
  red_flag: boolean;
  /** Mirrors the backend: red flags and unanswered questions escalate. */
  escalated: boolean;
};

const SMALL_TALK: Array<{ test: RegExp; reply: string }> = [
  {
    test: /^\s*(hi|hello|hey|hiya|good (morning|afternoon|evening))\b[\s!.?]*$/i,
    reply:
      "Hi, I'm Foggy! I answer questions from your care plan. Try asking when you can shower, how to manage swelling, or when you can drive.",
  },
  {
    test: /^\s*(thanks|thank you|thx|ty)\b.*$/i,
    reply: "Anytime. I'm here whenever a question pops up.",
  },
];

/** Keyword match against the care plan, with red-flag detection first. */
export function answerFromPlan(message: string, chunks: DemoChunk[] = DEMO_CARE_PLAN_CHUNKS): DemoAnswer {
  const text = message.toLowerCase();

  if (RED_FLAGS.some((flag) => text.includes(flag))) {
    return { content: EMERGENCY_REPLY, citations: [], answered_from_plan: false, red_flag: true, escalated: true };
  }

  const small = SMALL_TALK.find((s) => s.test.test(message));
  if (small) {
    return { content: small.reply, citations: [], answered_from_plan: true, red_flag: false, escalated: false };
  }

  const words = new Set((text.match(/[a-z']+/g) ?? []).filter((w) => w.length > 3));
  let best: DemoChunk | null = null;
  let bestHits = 0;
  for (const c of chunks) {
    const haystack = `${c.section ?? ""} ${c.content}`.toLowerCase();
    let hits = 0;
    words.forEach((w) => {
      if (haystack.includes(w)) hits += 1;
    });
    if (hits > bestHits) {
      best = c;
      bestHits = hits;
    }
  }

  if (!best) {
    return { content: NOT_IN_PLAN_REPLY, citations: [], answered_from_plan: false, red_flag: false, escalated: true };
  }

  return {
    content: `From your care plan: ${best.content}`,
    citations: [{ chunk_id: best.id, section: best.section ?? "Care plan" }],
    answered_from_plan: true,
    red_flag: false,
    escalated: false,
  };
}

export const DEMO_SUGGESTIONS = [
  "When can I shower?",
  "Is this much swelling normal?",
  "When can I drive again?",
  "Can I eat sushi?",
  "I have chest pain",
];

export const DEMO_WELCOME =
  "Hi Jordan, I'm Foggy. I only answer from the care plan Dr. Patel wrote for your knee replacement. Ask me anything about your recovery.";
