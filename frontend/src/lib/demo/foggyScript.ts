import type { ActionResult, ChatRoute, CheckinState, PendingAction } from "@/lib/api/types";

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
  /** Quick replies shown under a Foggy reply (display only). */
  chips?: string[];
  /** How long the typing indicator shows before this message (ms). */
  typingMs: number;
};

export const CONTACT_YES = "Yes, message my care team";
export const CONTACT_NO = "No thanks";

export const LANDING_SCRIPT: ScriptStep[] = [
  {
    from: "foggy",
    text: "Morning, Jordan, it’s day 3 after your knee surgery. What is your pain level from zero to ten?",
    typingMs: 1100,
  },
  { from: "patient", text: "Around a 4. Is it ok to shower today?", typingMs: 900 },
  {
    from: "foggy",
    text: "Your care plan says you can shower 48 hours after surgery with the waterproof dressing on. Do not soak in a bath, pool, or hot tub for 4 weeks.",
    cite: "Wound care",
    status: { tone: "logged", text: "Pain 4/10 logged" },
    typingMs: 1600,
  },
  { from: "patient", text: "Can I take ibuprofen too?", typingMs: 900 },
  {
    from: "foggy",
    text: "Your care plan does not mention ibuprofen. Would you like to contact your medical team?",
    chips: [CONTACT_YES, CONTACT_NO],
    typingMs: 1500,
  },
];

// ---------------------------------------------------------------------------
// 2. Local engine for the "Try texting Foggy" demo (no login, no network).
//    Mirrors the care-team contact policy with simple word rules. Nothing is
//    ever sent: agreeing to contact the care team returns a labeled simulation.
// ---------------------------------------------------------------------------

export const DEMO_WELCOME =
  "Hi Jordan, I'm Foggy, an AI recovery helper. I answer from the care plan your care team wrote for your knee replacement.";

export const DEMO_SUGGESTIONS = [
  "When can I shower?",
  "Can I eat sushi?",
  "Can I double my acetaminophen?",
  "Something feels off today",
  "I can't breathe",
];

export const EMERGENCY_REPLY = "Call 911 now. I can't place emergency calls.";
export const NOT_IN_PLAN_REPLY = "Your care plan does not cover that question. Would you like to contact your medical team?";
export const DOSE_CHANGE_REPLY = "I can't recommend changing your medicine. Would you like to contact your medical team?";
export const CALL_TEAM_PLAN_REPLY =
  "Your care plan says to call your medical team about this. Would you like help contacting them?";
/** Falls and numbness are a product rule, not in the written plan, so Foggy doesn't say the plan covers them. */
export const CALL_TEAM_RULE_REPLY = "Please call your medical team about this. Would you like help contacting them?";
export const IDENTITY_REPLY =
  "I'm an AI recovery helper, not a doctor or nurse. I can help explain your surgeon's care plan.";
export const DEMO_SENT_REPLY =
  "This is a demo, so no message was sent. In the live app, this would go to your medical team.";

const Q_PAIN = "What is your pain level from zero to ten?";
const Q_MEDS = "Have you taken your medicines as your care plan says?";
const Q_NUMB = "Have you had any new numbness, tingling, or change in skin color?";
const Q_FALL = "Have you had any falls since your surgery?";

type CheckinAnswers = { pain?: number; meds_taken?: boolean; missed?: string; numbness?: boolean; fall?: boolean };
type DemoCheckin = { step: 1 | 2 | 3 | 4; answers: CheckinAnswers; askedWhichMissed?: boolean };

export type DemoState = {
  pending: PendingAction | null;
  checkin: DemoCheckin | null;
  /** The contact offer was already repeated once after an unclear answer. */
  askedAgain: boolean;
};

export const INITIAL_DEMO_STATE: DemoState = { pending: null, checkin: null, askedAgain: false };

export type DemoReply = {
  content: string;
  route: ChatRoute;
  citations: Array<{ section: string }>;
  offerContact: boolean;
  actionResult: ActionResult | null;
  checkin: CheckinState | null;
};

type Turn = { reply: DemoReply; state: DemoState };

// ----- small text helpers -----

const NEGATION = /\b(no|not|never|without|don't|dont|didn't|didnt|haven't|havent|hasn't|hasnt|isn't|isnt|wasn't|aren't|denies|deny)\b/;
const HYPOTHETICAL = /\b(if|suppose|supposing|in case|hypothetically|example)\b/;

function normalize(text: string): string {
  return text.toLowerCase().replace(/[’‘`]/g, "'").replace(/\s+/g, " ").trim();
}

function clausesOf(text: string): string[] {
  return text.split(/[.!?;,]|\b(?:but|though|although|anyway)\b/).map((c) => c.trim()).filter(Boolean);
}

/** Finds a phrase that is reported, not denied ("no chest pain") and not hypothetical ("what if…"). */
function detect(text: string, patterns: RegExp[]): "real" | "hypothetical" | null {
  let hypothetical = false;
  for (const clause of clausesOf(text)) {
    for (const p of patterns) {
      const m = p.exec(clause);
      if (!m) continue;
      const before = clause.slice(0, m.index);
      if (NEGATION.test(before)) continue;
      if (HYPOTHETICAL.test(before)) {
        hypothetical = true;
        continue;
      }
      return "real";
    }
  }
  return hypothetical ? "hypothetical" : null;
}

const EMERGENCY: RegExp[] = [
  /chest (pain|hurts?|pressure|tightness|is tight|feels tight)/,
  /my chest (hurts|is hurting|aches)/,
  /pain in my chest/,
  /(can't|cannot|can not|couldn't|unable to|not able to) (breathe|catch my breath|get (enough )?air)/,
  /(trouble|difficulty|hard time|struggling|problems?) breathing/,
  /hard to breathe/,
  /short(ness)? of breath/,
  /out of breath/,
  /(heavy|heavily|lots of|a lot of) (bleeding|blood)/,
  /bleeding (heavily|a lot|badly|through)/,
  /(won't|wont|will not|doesn't|does not) stop bleeding/,
  /\bfaint(ed|ing)?\b/,
  /passed out/,
  /black(ed)? out/,
  /lost consciousness|unconscious/,
  /\b(please call|can you call|could you call|help me call|i need to call|i need|call) (911|an ambulance) (for me|now|right now)\b/,
  /\b(please call|can you call|could you call|help me call|i need to call|i need) (911|an ambulance)\b/,
  /suicid|kill myself|end my life/,
];

const PLAN_TRIGGERS: RegExp[] = [
  /redness|redder|getting red|more red|red around/,
  /drainage|draining|oozing|\bpus\b|discharge/,
  /calf.{0,25}(pain|hurt|sore|swell|swollen|tender|tight)/,
  /(pain|swelling|swollen|sore|tender)\b.{0,15}\bcalf/,
  /(uncontrolled|out of control|not controlled|can't control|cannot control|unbearable|excruciating|worst pain)/,
  /pain (medicine|medication|meds|pills?) (isn't|is not|aren't|are not) (helping|working)/,
];

const RULE_TRIGGERS: RegExp[] = [
  /\b(i fell|i've fallen|i have fallen|had a fall|took a fall|tripped and fell|fell (down|over|getting|out|in|on|off|while|when|this|last|yesterday|today))\b/,
  /\b(numb|numbness|tingl\w*|pins and needles)\b/,
  /\b(turn(ed|ing)?|look(s|ing)?|is|gone) (blue|white|pale|purple|gr[ae]y)\b/,
  /(different|new|strange|weird|odd) colou?r|colou?r change|chang\w* colou?r/,
];

const MED_CONTEXT =
  /\b(acetaminophen|tylenol|oxycodone|oxy|opioids?|aspirin|medicines?|medications?|meds|pills?|doses?|dosage|mg|milligrams?)\b/;
const DOSE_CHANGE =
  /\b(double|extra|(take|have|use|get) (\w+ )?(more|less|fewer)|more (often|pills?|doses?)|skip|stop|stopping|quit|half|instead of|increase|decrease|lower|higher|cut (back|down)|another (pill|dose)|go off|come off|twice as much|two times as much)\b/;
const MISSED = /\b(missed|forgot|forgotten|skipped|didn't take|did not take|haven't taken)\b/;
const NOT_MISSED = /\b(haven't|have not|didn't|did not|never) (missed|forgot|skipped)\b/;
const UNLISTED =
  /\b(ibuprofen|advil|motrin|aleve|naproxen|benadryl|melatonin|supplements?|vitamins?|herbal|alcohol|wine|beer|liquor|cocktails?|cannabis|marijuana|weed|cbd|thc|edibles?|sleeping pills?|antibiotics?)\b/;
const MED_NAMES = /\b(ibuprofen|advil|motrin|aleve|naproxen|benadryl|melatonin)\b/;

const YES = /^(yes|yeah|yep|yup|ya|sure|ok|okay|please|please do|yes please|do it|go ahead|i have|i did|i do|correct|of course|y)\b/;
const NO = /^(no|nope|nah|not really|none|never|nothing|i haven't|i have not|i didn't|n)\b/;
const CONTACT_CONSENT =
  /^(yes|yeah|yep|yup|sure|ok|okay|please|please do|yes please|do it|go ahead|yes,? (please )?(message|contact) my (care|medical) team|(message|contact) my (care|medical) team)[.! ]*$/;
const CONTACT_DECLINE = /^(no|nope|nah|no thanks|no thank you|not now|not right now|don't|do not|no,? (that's|i'm) (ok|okay|fine))[.! ]*$/;
const UNCLEAR = /^(maybe|not sure|i'm not sure|i don't know|idk|hmm+|um+|unsure|i guess|perhaps)[.!? ]*$/;
const CONTACT_REQUEST =
  /\b(message|contact|text|email|reach|talk to|speak (to|with)) (my |the )?(care team|medical team|surgeon|doctor|nurse|dr\.? patel)\b/;
const CALL_REQUEST = /\b(call|phone|ring) (my |the )?(care team|medical team|surgeon|doctor|nurse|dr\.? patel)\b/;

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

function painNumber(text: string): number | null {
  const m = /\b(10|[0-9])\b/.exec(text);
  if (m) return Number(m[1]);
  for (let i = NUMBER_WORDS.length - 1; i >= 0; i -= 1) {
    if (new RegExp(`\\b${NUMBER_WORDS[i]}\\b`).test(text)) return i;
  }
  return null;
}

/** A pain score volunteered outside the check-in ("my pain is a 6", "6/10"). */
function volunteeredPain(text: string): number | null {
  const m =
    /\bpain(?: level)?(?: is| was| at| of| around| about| like)+(?: a| an)? (10|[0-9]|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b/.exec(
      text,
    ) ?? /\b(10|[0-9])\s*(?:\/|out of)\s*10\b/.exec(text);
  const v = m?.[1];
  if (!v) return null;
  return /^\d+$/.test(v) ? Number(v) : NUMBER_WORDS.indexOf(v);
}

/** Temperatures between 90 and 110 °F mentioned with a fever or temperature word. */
function temperatures(text: string): number[] {
  if (!/(fever|temp|temperature|°|degrees|fahrenheit)/.test(text)) return [];
  return Array.from(text.matchAll(/\b(\d{2,3}(?:\.\d+)?)\b/g))
    .map((m) => Number(m[1]))
    .filter((n) => n >= 90 && n <= 110);
}

// ----- reply builders -----

function reply(content: string, route: ChatRoute, extra: Partial<DemoReply> = {}): DemoReply {
  return { content, route, citations: [], offerContact: false, actionResult: null, checkin: null, ...extra };
}

function fromPlan(content: string, section: string): DemoReply {
  return reply(content, "ANSWER_FROM_PLAN", { citations: [{ section }] });
}

/** A reply that offers to contact the care team; the next "yes" is consent to exactly this. */
function offer(content: string, route: ChatRoute, reason: string, state: DemoState): Turn {
  return {
    reply: reply(content, route, { offerContact: true }),
    state: { ...state, checkin: null, askedAgain: false, pending: { kind: "message_care_team", recipient: "care_team", reason } },
  };
}

function plain(r: DemoReply, state: DemoState): Turn {
  return { reply: r, state: { ...state, pending: null, askedAgain: false } };
}

function checkinTurn(content: string, checkin: DemoCheckin, state: DemoState, route: ChatRoute = "START_CHECKIN"): Turn {
  return {
    reply: reply(content, route, { checkin: { step: checkin.step, answers: { ...checkin.answers } } }),
    state: { ...state, pending: null, askedAgain: false, checkin },
  };
}

// ----- routing -----

/** Plan call triggers and the product rule for falls / numbness. Null when none apply. */
function callTrigger(text: string, state: DemoState): Turn | null {
  const temps = temperatures(text);
  const feverWord = detect(text, [/\bfever\b/]);
  if (temps.some((t) => t > 101.5) && feverWord !== "hypothetical") {
    return offer(CALL_TEAM_PLAN_REPLY, "CALL_SURGEON", "Temperature over 101.5 F", state);
  }
  if (temps.length === 0 && feverWord === "real") {
    return offer(
      "Your care plan says to call your medical team for a fever over 101.5 F. Would you like help contacting them?",
      "CALL_SURGEON",
      "Fever",
      state,
    );
  }
  const plan = detect(text, PLAN_TRIGGERS);
  if (plan === "real") return offer(CALL_TEAM_PLAN_REPLY, "CALL_SURGEON", "Care plan call trigger", state);
  const rule = /fell asleep|fall asleep/.test(text) ? null : detect(text, RULE_TRIGGERS);
  if (rule === "real") return offer(CALL_TEAM_RULE_REPLY, "CALL_SURGEON", "Fall or new numbness, tingling, or color change", state);
  if (plan === "hypothetical" || rule === "hypothetical") {
    return plain(
      fromPlan(
        "Your care plan says to call your surgeon for a fever over 101.5 F, more redness or drainage, calf pain or swelling, or pain your medicine does not control. Call 911 for chest pain or trouble breathing.",
        "When to call",
      ),
      state,
    );
  }
  return null;
}

/** Everything after emergencies, consent, and the check-in. Null means "not covered". */
function routeQuestion(text: string, state: DemoState): Turn | null {
  const trigger = callTrigger(text, state);
  if (trigger) return trigger;

  if (MED_CONTEXT.test(text) && MISSED.test(text)) {
    return offer(
      "Your care plan does not say what to do after a missed dose. Would you like to contact your medical team?",
      "NOT_IN_PLAN",
      "Missed dose",
      state,
    );
  }
  if (MED_CONTEXT.test(text) && DOSE_CHANGE.test(text)) {
    return offer(DOSE_CHANGE_REPLY, "REFUSE_DOSE_CHANGE", "Medicine change question", state);
  }
  const unlisted = UNLISTED.exec(text);
  if (unlisted) {
    const name = MED_NAMES.test(unlisted[1]) ? unlisted[1] : "that";
    return offer(
      `Your care plan does not mention ${name}. Would you like to contact your medical team?`,
      "NOT_IN_PLAN",
      "Medicine or substance not in the plan",
      state,
    );
  }

  if (/\b(are you (a |an )?(real )?(doctor|nurse|human|person|robot|bot|ai|machine))\b|\bwho are you\b|\bwhat are you\b|\bare you real\b/.test(text)) {
    return plain(reply(IDENTITY_REPLY, "OPERATIONAL"), state);
  }
  if (CALL_REQUEST.test(text)) {
    return offer(
      "I can't place phone calls, but I can send a message to your care team. Would you like me to do that?",
      "OPERATIONAL",
      "Patient asked to contact the care team",
      state,
    );
  }
  if (CONTACT_REQUEST.test(text)) {
    return offer(
      "I can send a message to your care team. Would you like me to do that?",
      "OPERATIONAL",
      "Patient asked to contact the care team",
      state,
    );
  }

  if (/\b(check[- ]?in|feel(ing)? off|something (feels|is) off|not feeling (right|well|myself)|feel (weird|strange|funny|wrong))\b/.test(text)) {
    const pain = volunteeredPain(text);
    if (pain !== null) {
      return checkinTurn(`Let's do a short check-in, Jordan. ${Q_MEDS}`, { step: 2, answers: { pain } }, state);
    }
    return checkinTurn(`Let's do a short check-in, Jordan. ${Q_PAIN}`, { step: 1, answers: {} }, state);
  }
  const pain = volunteeredPain(text);
  if (pain !== null) {
    return checkinTurn(`Thanks, I noted pain ${pain} out of 10. ${Q_MEDS}`, { step: 2, answers: { pain } }, state);
  }

  if (/\bmy (sister|brother|mom|mother|dad|father|wife|husband|son|daughter|friend|kid|child|partner|grandma|grandmother|grandpa|grandfather|aunt|uncle|cousin|neighbor|roommate)\b/.test(text)) {
    return offer(
      "Your care plan is only for you, so I can't answer for someone else. Would you like to contact your medical team?",
      "NOT_IN_PLAN",
      "Question about someone else",
      state,
    );
  }
  if (/(wrong (treatment|surgery|choice|decision)|second opinion|bad (surgeon|doctor)|made a mistake|picked the wrong)/.test(text)) {
    return offer(
      "I can't give a second opinion about your treatment. Would you like to contact your medical team?",
      "NOT_IN_PLAN",
      "Second opinion",
      state,
    );
  }
  if (/\b(go back to work|return to work|back to work|my job|desk job|the office|fly|flying|flight|airplane|plane|travel|traveling|travelling|vacation|trip)\b/.test(text)) {
    return offer(
      "Your care plan does not say when you can go back to work or travel. Would you like to contact your medical team?",
      "NOT_IN_PLAN",
      "Work or travel",
      state,
    );
  }
  if (/\b(scared|afraid|anxious|anxiety|worried|nervous|sad|depressed|lonely|overwhelmed|stressed|frightened)\b/.test(text)) {
    return offer(
      "I'm sorry this feels hard, Jordan. Would you like to contact your medical team about how you're feeling?",
      "NOT_IN_PLAN",
      "Patient shared how they are feeling",
      state,
    );
  }
  if (/\b(joke|weather|game|score|movie|song|music|news|recipe|stocks?|sports|who won|capital of|president)\b/.test(text)) {
    return offer(
      "I can only help with your recovery care plan. Would you like to contact your medical team?",
      "NOT_IN_PLAN",
      "Unrelated question",
      state,
    );
  }
  if (/^(hi|hello|hey|hiya|good (morning|afternoon|evening))\b[\s!.?]*(foggy)?[\s!.?]*$/.test(text)) {
    return plain(
      reply("Hi Jordan, I'm here to help with your care plan. You can ask things like when you can shower or drive.", "OPERATIONAL"),
      state,
    );
  }
  if (/^(thanks|thank you|thx|ty)\b/.test(text)) {
    return plain(reply("You're welcome, Jordan. I'm here if you have another question.", "OPERATIONAL"), state);
  }

  const topic = planTopic(text);
  if (!topic) return null;
  return topic.offerContact ? offer(topic.content, topic.route, "Detail not in the care plan", state) : plain(topic, state);
}

/** Covered questions: keyword match to the demo plan sections, phrased in two sentences or fewer. */
function planTopic(text: string): DemoReply | null {
  const oxy = /\b(oxycodone|oxy|opioids?)\b/.test(text);
  if (oxy && /(how often|how many hours|hours between|between doses|how long between|maximum|\bmax\b|how many (pills|a day|per day|times))/.test(text)) {
    return reply(
      "Your care plan does not give a time between oxycodone doses or a daily limit. Would you like to contact your medical team?",
      "NOT_IN_PLAN",
      { offerContact: true },
    );
  }
  if (/\b(drive|driving|car)\b/.test(text)) {
    return fromPlan(
      "Your care plan says no driving for 4 weeks. It also says not to drive while taking opioid pain medicine like oxycodone.",
      "Activity",
    );
  }
  if (/\b(shower|showering|bath|bathe|soak|soaking|pool|hot tub|swim|swimming|wash|wet)\b/.test(text)) {
    return fromPlan(
      "Your care plan says you can shower 48 hours after surgery with the waterproof dressing on. Do not soak in a bath, pool, or hot tub for 4 weeks.",
      "Wound care",
    );
  }
  if (/\b(dressing|bandage|incision|wound|stitches|staples|scar)\b/.test(text)) {
    return fromPlan("Your care plan says to keep the incision clean and dry. Change the dressing every 2 days.", "Wound care");
  }
  if (/\b(walk|walking|walker|exercise|exercises|therapy|pt|activity|active)\b/.test(text)) {
    return fromPlan(
      "Your care plan says to walk with your walker at least 3 times a day. Do your physical therapy exercises twice a day.",
      "Activity",
    );
  }
  if (/\b(ice|icing|cold pack|elevate|elevating|elevated|raise|raising|leg up|prop)\b/.test(text)) {
    return fromPlan(
      "Your care plan says to ice your knee 20 minutes at a time, several times a day. Keep your leg raised above heart level when resting.",
      "Pain and swelling",
    );
  }
  if (/\b(swell\w*|swollen|bruis\w*)\b/.test(text)) {
    return fromPlan(
      "Your care plan says some swelling and bruising is expected for 2 to 3 weeks. It says to ice your knee and keep your leg raised above heart level.",
      "Pain and swelling",
    );
  }
  if (/\b(acetaminophen|tylenol)\b/.test(text)) {
    return fromPlan("Your care plan says to take acetaminophen 1000 mg every 8 hours.", "Medications");
  }
  if (oxy) {
    return fromPlan("Your care plan says to take oxycodone 5 mg only as needed for severe pain.", "Medications");
  }
  if (/\b(aspirin|blood clots?)\b/.test(text)) {
    return fromPlan("Your care plan says to take aspirin 81 mg twice a day for 4 weeks to help prevent blood clots.", "Medications");
  }
  if (/\b(medicines?|medications?|meds|pills|prescriptions?)\b/.test(text)) {
    return fromPlan(
      "Your care plan lists acetaminophen 1000 mg every 8 hours and oxycodone 5 mg only as needed for severe pain. It also lists aspirin 81 mg twice a day for 4 weeks.",
      "Medications",
    );
  }
  if (/\b(fever|temperature|temp|warning signs?|when (should|do) i call|call (my|the) (surgeon|doctor))\b/.test(text)) {
    return fromPlan(
      "Your care plan says to call your surgeon for a fever over 101.5 F, more redness or drainage, calf pain or swelling, or pain your medicine does not control. Call 911 for chest pain or trouble breathing.",
      "When to call",
    );
  }
  if (/\b(pain|hurts?|sore|ache|aching)\b/.test(text) && !/\bchest\b/.test(text)) {
    return fromPlan(
      "Your care plan says to ice your knee 20 minutes at a time and keep your leg raised above heart level. It lists acetaminophen 1000 mg every 8 hours and oxycodone 5 mg only as needed for severe pain.",
      "Pain and swelling",
    );
  }
  return null;
}

/** One check-in step. Returns null when the message is not an answer to the current question. */
function checkinStep(text: string, c: DemoCheckin, state: DemoState): Turn | null {
  const answers = { ...c.answers };
  switch (c.step) {
    case 1: {
      const n = painNumber(text);
      if (n === null) {
        if (/\b(pain|hurts?|sore|ache|bad|okay|ok|fine|good|not great)\b/.test(text)) {
          return checkinTurn("Thanks. Can you give it a number from zero to ten?", c, state);
        }
        return null;
      }
      answers.pain = n;
      return checkinTurn(`Thanks, Jordan. ${Q_MEDS}`, { step: 2, answers }, state);
    }
    case 2: {
      if (c.askedWhichMissed) {
        answers.missed = text.slice(0, 80);
        return checkinTurn(`Okay. ${Q_NUMB}`, { step: 3, answers }, state);
      }
      if (NOT_MISSED.test(text)) {
        answers.meds_taken = true;
        return checkinTurn(`Got it. ${Q_NUMB}`, { step: 3, answers }, state);
      }
      if (MISSED.test(text) || NO.test(text) || /\bnot all\b/.test(text)) {
        answers.meds_taken = false;
        const named = /\b(acetaminophen|tylenol|oxycodone|aspirin)\b/.exec(text);
        if (named) {
          answers.missed = named[1];
          return checkinTurn(`Thanks for telling me. ${Q_NUMB}`, { step: 3, answers }, state);
        }
        return checkinTurn("Thanks for telling me. Which medicine did you miss?", { step: 2, answers, askedWhichMissed: true }, state);
      }
      if (YES.test(text)) {
        answers.meds_taken = true;
        return checkinTurn(`Got it. ${Q_NUMB}`, { step: 3, answers }, state);
      }
      return null;
    }
    case 3: {
      if (YES.test(text) || /\b(a little|some|kind of|a bit)\b/.test(text)) {
        return offer(CALL_TEAM_RULE_REPLY, "CALL_SURGEON", "New numbness, tingling, or color change", state);
      }
      if (NO.test(text)) {
        answers.numbness = false;
        return checkinTurn(`Okay. ${Q_FALL}`, { step: 4, answers }, state);
      }
      return null;
    }
    case 4: {
      if (YES.test(text)) return offer(CALL_TEAM_RULE_REPLY, "CALL_SURGEON", "Fall reported in check-in", state);
      if (NO.test(text)) {
        answers.fall = false;
        return {
          reply: reply("Thanks for checking in, Jordan.", "OPERATIONAL", { checkin: { step: "done", answers } }),
          state: { ...state, pending: null, checkin: null, askedAgain: false },
        };
      }
      return null;
    }
  }
}

const CHECKIN_QUESTION: Record<DemoCheckin["step"], string> = { 1: Q_PAIN, 2: Q_MEDS, 3: Q_NUMB, 4: Q_FALL };

/**
 * One demo turn. Priority: emergency, then a pending contact offer, then the
 * check-in, then plan call triggers, medicine rules, and plan questions.
 */
export function demoTurn(message: string, state: DemoState): Turn {
  const text = normalize(message);

  // 1. Emergencies first, always. Ends any check-in or pending offer.
  const emergency = detect(text, EMERGENCY);
  if (emergency === "real") {
    return { reply: reply(EMERGENCY_REPLY, "EMERGENCY_911"), state: INITIAL_DEMO_STATE };
  }

  // 2. An answer to a pending contact offer. Only a plain yes counts as consent.
  if (state.pending) {
    if (CONTACT_CONSENT.test(text)) {
      return {
        reply: reply(DEMO_SENT_REPLY, "OPERATIONAL", {
          actionResult: { kind: "message_care_team", status: "simulated", detail: "Demo: nothing was sent" },
        }),
        state: { ...state, pending: null, askedAgain: false },
      };
    }
    if (CONTACT_DECLINE.test(text)) {
      return plain(reply("Okay, I won't send anything. I'm here if you have another question.", "OPERATIONAL"), state);
    }
    if (UNCLEAR.test(text) && !state.askedAgain) {
      return {
        reply: reply("Would you like me to message your care team? Please answer yes or no.", "OPERATIONAL", {
          offerContact: true,
        }),
        state: { ...state, askedAgain: true },
      };
    }
  }

  // 3. The check-in, one question at a time. Call triggers interrupt it.
  if (state.checkin) {
    const trigger = callTrigger(text, state);
    if (trigger) return trigger;
    const step = checkinStep(text, state.checkin, state);
    if (step) return step;
    // Not an answer: handle a different question (this ends the check-in), or ask again.
    const other = routeQuestion(text, { ...state, checkin: null });
    if (other) return other;
    const c = state.checkin;
    const question = c.step === 2 && c.askedWhichMissed ? "Which medicine did you miss?" : CHECKIN_QUESTION[c.step];
    return checkinTurn(`Sorry, I didn't catch that. ${question}`, c, state);
  }

  if (emergency === "hypothetical") {
    return plain(reply("If that ever happens, call 911 right away. I can't place emergency calls.", "OPERATIONAL"), state);
  }

  if (!state.pending && (CONTACT_CONSENT.test(text) || CONTACT_DECLINE.test(text))) {
    if (/(message|contact) my (care|medical) team/.test(text)) {
      return offer(
        "I can send a message to your care team. Would you like me to do that?",
        "OPERATIONAL",
        "Patient asked to contact the care team",
        state,
      );
    }
    return plain(reply("Okay. What would you like to know about your recovery?", "OPERATIONAL"), state);
  }

  const routed = routeQuestion(text, state);
  if (routed) return routed;
  // A denial ("no chest pain") is not a report and not a question.
  if (EMERGENCY.some((p) => p.test(text))) {
    return plain(reply("Thanks for telling me. What would you like to know about your care plan?", "OPERATIONAL"), state);
  }
  return offer(NOT_IN_PLAN_REPLY, "NOT_IN_PLAN", "Question not covered by the care plan", state);
}
