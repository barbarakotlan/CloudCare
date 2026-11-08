import { ApiError, apiFetch } from "./client";

/**
 * Sales chat ("talk to Barbara") and pilot requests from hospital visitors.
 * Public routes: no sign-in, no patient data.
 *
 * Graceful degradation: when the server does not have the sales routes yet
 * (404), chat answers come from a small local script so the bubble still
 * works. Pilot requests are only faked in development; in production a missing
 * route is reported as an error, because telling a visitor "we got it" when
 * nothing was stored would be untrue.
 */

export type SalesRole = "user" | "assistant";
export type SalesTurn = { role: SalesRole; content: string };

export type SalesChatIn = {
  session_id: string;
  message: string;
  history: SalesTurn[];
  page?: string;
};

export type SalesChatOut = {
  reply: string;
  suggestions: string[];
  cta: "onboard" | null;
  provider: "gemini" | "rules" | "local";
};

export type SalesLeadIn = {
  session_id: string;
  hospital: string;
  contact_name: string;
  role: string;
  work_email: string;
  phone?: string;
  discharges_per_month?: string;
  ehr?: string;
  service_lines?: string;
  timeline?: string;
  notes?: string;
  transcript?: SalesTurn[];
  /** Honeypot: people never see or fill it. */
  website?: string;
  /** Page the request was sent from. */
  page?: string;
};

export type SalesLeadOut = {
  id: string;
  status: "stored";
  email?: { to: string; subject: string; body: string };
};

export const SALES_HISTORY_LIMIT = 12;
export const SALES_TRANSCRIPT_LIMIT = 40;

export async function sendSalesChat(body: SalesChatIn, signal?: AbortSignal): Promise<SalesChatOut> {
  const payload: SalesChatIn = { ...body, history: body.history.slice(-SALES_HISTORY_LIMIT) };
  try {
    return await apiFetch<SalesChatOut>("/sales/chat", { method: "POST", body: payload, auth: false, signal });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return localReply(body.message);
    throw err;
  }
}

export async function submitSalesLead(body: SalesLeadIn): Promise<SalesLeadOut> {
  const payload: SalesLeadIn = { ...body, transcript: body.transcript?.slice(-SALES_TRANSCRIPT_LIMIT) };
  try {
    return await apiFetch<SalesLeadOut>("/sales/leads", { method: "POST", body: payload, auth: false });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404 && process.env.NODE_ENV !== "production") {
      return { id: `local-${Date.now()}`, status: "stored" };
    }
    throw err;
  }
}

/* ------------------------------------------------------------------ */
/* Local fallback answers (used only when the server has no /sales).  */
/* ------------------------------------------------------------------ */

type Rule = { test: RegExp; reply: string; suggestions: string[]; cta?: "onboard" };

const RULES: Rule[] = [
  {
    test: /\b(price|pricing|cost|costs|quote|budget|how much|fee|license)\b/i,
    reply:
      "Pricing depends on your discharge volume and integration scope, so a person on our team walks you through it. Most hospitals start with a small pilot on one procedure. Want me to get your hospital set up? It takes two minutes.",
    suggestions: ["What does a pilot look like?", "How does it work with Epic?"],
    cta: "onboard",
  },
  {
    test: /\b(pilot|onboard|onboarding|sign up|signup|get started|start|trial|demo for|our hospital|my hospital)\b/i,
    reply:
      "Most teams pilot with one procedure first, often a joint replacement or general surgery line, and expand once the care team trusts the workflow. Want me to get your hospital set up? It takes two minutes.",
    suggestions: ["What does it cost?", "How does it work with Epic?"],
    cta: "onboard",
  },
  {
    test: /\b(epic|mychart|ehr|cerner|oracle|meditech|fhir|integrat)/i,
    reply:
      "Patients can connect their Epic MyChart account through SMART on FHIR, so CloudCare sees their medications, labs and visits without manual uploads. Today that runs against Epic's sandbox; production access is part of a pilot. Want to hear how a pilot works?",
    suggestions: ["What does a pilot look like?", "Is it HIPAA compliant?"],
  },
  {
    test: /\b(hipaa|baa|security|privacy|fda|complian|regulat)/i,
    reply:
      "Honest answer: CloudCare is at the demo stage, it has not been reviewed by the FDA, and we are not operating under HIPAA or signed BAAs yet. Those come before any real patient data, and our team will walk your compliance people through the plan.",
    suggestions: ["What does a pilot look like?", "Ready to onboard"],
  },
  {
    test: /\b(human|real person|bot|ai|robot|are you)\b/i,
    reply:
      "I'm Barbara's AI twin, speaking for her while she's busy; a real person on our team follows up on every pilot request. What would you like to know about CloudCare?",
    suggestions: ["How does it work with Epic?", "What does it cost?"],
  },
  {
    test: /\b(how|what is|what does|work|foggy|patients?|feature)/i,
    reply:
      "Your clinicians upload the discharge plan, and Foggy follows up with patients by text and voice, answering only from that plan. Red flags get 911 wording, and anything the plan does not cover is offered to the care team's queue with the patient's consent.",
    suggestions: ["How does it work with Epic?", "What does it cost?"],
  },
];

const DEFAULT_RULE: Omit<Rule, "test"> = {
  reply:
    "Good question; the person on our team who runs your pilot can go deeper on that. In short, CloudCare brings the care team's discharge plan home with patients and flags what needs a human. Are you looking at this for a surgical service line?",
  suggestions: ["How does it work with Epic?", "What does it cost?", "Ready to onboard"],
};

function localReply(message: string): SalesChatOut {
  const rule = RULES.find((r) => r.test.test(message)) ?? DEFAULT_RULE;
  return { reply: rule.reply, suggestions: rule.suggestions, cta: rule.cta ?? null, provider: "local" };
}
