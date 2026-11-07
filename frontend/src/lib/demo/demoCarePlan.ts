/**
 * Copy of DEMO_CARE_PLAN from backend/app/seed.py (Jordan Lee, total knee
 * replacement). Used by the landing-page demo chat, which runs without login.
 * Keep in sync with the backend seed if it changes.
 */

export const DEMO_CARE_PLAN_TITLE = "Total Knee Replacement: Home Recovery";

export const DEMO_CARE_PLAN_TEXT = `Wound care:
Keep the incision clean and dry. You may shower 48 hours after surgery with the waterproof dressing on. Do not soak in a bath, pool or hot tub for 4 weeks. Change the dressing every 2 days.

Activity:
Walk with your walker at least 3 times a day. Do your physical therapy exercises twice daily. No driving for 4 weeks or while taking opioid pain medicine.

Pain and swelling:
Ice the knee 20 minutes at a time, several times a day. Keep your leg elevated above heart level when resting. Some swelling and bruising is normal for 2 to 3 weeks.

Medications:
Take Acetaminophen 1000 mg every 8 hours. Take Oxycodone 5 mg only as needed for severe pain. Take Aspirin 81 mg twice daily for 4 weeks to prevent blood clots.

When to call:
Call your surgeon if you have a fever over 101.5 F, increasing redness or drainage from the incision, calf pain or swelling, or pain not controlled by medication. Call 911 for chest pain or trouble breathing.`;

export type DemoChunk = { id: string; chunk_index: number; section: string | null; content: string };

/** Same rule as split_into_chunks() in backend/app/routes/patients.py. */
export function splitIntoChunks(rawText: string): Array<{ section: string | null; content: string }> {
  const chunks: Array<{ section: string | null; content: string }> = [];
  for (const block of rawText.replace(/\r\n/g, "\n").split("\n\n").map((b) => b.trim())) {
    if (!block) continue;
    const nl = block.indexOf("\n");
    const first = nl >= 0 ? block.slice(0, nl) : block;
    const rest = nl >= 0 ? block.slice(nl + 1).trim() : "";
    if (first.endsWith(":") && first.length <= 60 && rest) {
      chunks.push({ section: first.slice(0, -1).trim(), content: rest });
    } else {
      chunks.push({ section: null, content: block });
    }
  }
  return chunks;
}

export const DEMO_CARE_PLAN_CHUNKS: DemoChunk[] = splitIntoChunks(DEMO_CARE_PLAN_TEXT).map((c, i) => ({
  id: `demo-chunk-${i}`,
  chunk_index: i,
  ...c,
}));
