import transcript from "../../../public/audio/foggy-demo-call.transcript.json";
import { CallPlayer, type TranscriptLine } from "./CallPlayer";

/**
 * Transcript lines come from public/audio/foggy-demo-call.transcript.json
 * (speech-to-text with word timestamps, merged into sentences). Edit the
 * `speaker` or `text` fields there if a label or word needs correcting.
 */
const LINES: TranscriptLine[] = transcript;
/** Length of the MP3 in seconds; the player replaces it with the file's own metadata once loaded. */
const DURATION = 82.44;

export function HearFoggy() {
  return (
    <section id="hear-a-call" aria-labelledby="hear-title" className="scroll-mt-20 px-4 pb-16 sm:px-6 sm:pb-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-extrabold tracking-[0.14em] text-brand-cyan-strong uppercase">Listen in</p>
          <h2 id="hear-title" className="mt-3 text-3xl leading-tight font-black tracking-tight text-balance text-ink sm:text-5xl">
            Hear a real check-in call.
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-ink-soft text-pretty">
            Foggy calls after discharge, asks about pain and medicines one question at a time, checks for warning signs,
            and passes a summary to the care team when the patient asks.
          </p>
          <p className="mt-3 text-sm font-semibold text-brand-gray">Recorded demo call with a fictional patient.</p>
        </div>

        <div className="mt-10 sm:mt-12">
          <CallPlayer src="/audio/foggy-demo-call.mp3" lines={LINES} fallbackDuration={DURATION} />
        </div>
      </div>
    </section>
  );
}
