"use client";

import { Pause, Play, Volume2, VolumeX } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type CSSProperties } from "react";
import { FoggyAvatar } from "@/components/chat/FoggyAvatar";
import { cn } from "@/lib/cn";
import { useReducedMotion } from "@/lib/hooks/useReducedMotion";

export type TranscriptLine = { start: number; end: number; speaker: string; text: string };

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function spokenTime(seconds: number): string {
  const s = Math.floor(Math.max(0, seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m} minute${m === 1 ? "" : "s"} ${r} second${r === 1 ? "" : "s"}` : `${r} second${r === 1 ? "" : "s"}`;
}

/**
 * Seconds added to the playback clock before matching it against the transcript
 * timestamps. 0 = the speech-to-text timings are used as-is (checked against the
 * audio's own speech onsets, which line up within ~0.1 s).
 */
const SYNC_OFFSET = 0;

/** Index of the line being spoken at time t; stays on a line through the pause after it. */
function activeIndex(lines: TranscriptLine[], t: number): number {
  let idx = -1;
  for (let i = 0; i < lines.length; i += 1) {
    if (lines[i].start <= t + SYNC_OFFSET + 0.05) idx = i;
    else break;
  }
  return idx;
}

/**
 * Audio player for the recorded demo call with a transcript that follows
 * playback. Built on a plain <audio> element: no autoplay, metadata preload only.
 */
export function CallPlayer({
  src,
  lines,
  fallbackDuration,
}: {
  src: string;
  lines: TranscriptLine[];
  fallbackDuration: number;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const lineRefs = useRef<Array<HTMLLIElement | null>>([]);
  const reduced = useReducedMotion();

  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(fallbackDuration);
  const [failed, setFailed] = useState(false);
  const [started, setStarted] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const current = started ? activeIndex(lines, time) : -1;
  // Lines appear as the recording reaches them; scrubbing back hides the later ones again.
  // "Show full transcript" (or a recording that can't play) reveals everything.
  const revealAll = showAll || failed;
  const visibleCount = revealAll ? lines.length : current + 1;

  // The server-rendered <audio> can load its metadata (or fail) before React attaches handlers.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.error) setFailed(true);
    else if (audio.readyState >= 1 && Number.isFinite(audio.duration) && audio.duration > 0) setDuration(audio.duration);
  }, []);

  // Smooth clock while playing (timeupdate alone only fires a few times a second).
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      const audio = audioRef.current;
      if (audio) setTime(audio.currentTime);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  // Keep the spoken line in view inside the transcript box (never scrolls the page).
  // While following the call the newest line sits at the bottom, like a chat.
  useEffect(() => {
    if (current < 0) return;
    const list = listRef.current;
    const item = lineRefs.current[current];
    if (!list || !item) return;
    const top = revealAll
      ? item.offsetTop - list.clientHeight / 2 + item.clientHeight / 2
      : item.offsetTop + item.offsetHeight - list.clientHeight + 16;
    list.scrollTo({ top: Math.max(0, top), behavior: reduced ? "auto" : "smooth" });
  }, [current, revealAll, reduced]);

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      setStarted(true);
      void audio.play().catch(() => setFailed(true));
    } else {
      audio.pause();
    }
  }, []);

  const seek = useCallback((t: number, play: boolean) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = t;
    setTime(t);
    setStarted(true);
    if (play && audio.paused) void audio.play().catch(() => setFailed(true));
  }, []);

  const onScrub = (e: ChangeEvent<HTMLInputElement>) => seek(Number(e.target.value), false);

  const toggleMute = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.muted = !audio.muted;
    setMuted(audio.muted);
  };

  const pct = duration > 0 ? Math.min(100, (time / duration) * 100) : 0;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-start lg:gap-8">
      {/* Player card */}
      <div className="rounded-[2rem] bg-white p-5 shadow-soft ring-1 ring-line sm:p-6">
        <audio
          ref={audioRef}
          src={src}
          preload="metadata"
          onLoadedMetadata={(e) => {
            const d = e.currentTarget.duration;
            if (Number.isFinite(d) && d > 0) setDuration(d);
          }}
          onPlay={() => {
            // Also covers playback started outside our button (media keys, OS controls).
            setStarted(true);
            setPlaying(true);
          }}
          onPause={() => setPlaying(false)}
          onEnded={(e) => {
            setPlaying(false);
            setTime(e.currentTarget.duration);
          }}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onError={() => setFailed(true)}
        />

        <div className="flex items-center gap-3">
          <FoggyAvatar size={44} decorative />
          <div className="min-w-0">
            <p className="font-extrabold text-ink">Foggy check-in call</p>
            <p className="text-sm text-brand-gray">Outbound call · {formatTime(duration)}</p>
          </div>
          {playing ? (
            <span aria-hidden="true" className="ml-auto flex h-5 items-end gap-0.5">
              {[0, 180, 360, 540].map((d) => (
                <span
                  key={d}
                  className={cn("w-1 rounded-full bg-brand-cyan", reduced ? "h-3" : "h-5 animate-typing")}
                  style={reduced ? undefined : { animationDelay: `${d}ms` }}
                />
              ))}
            </span>
          ) : null}
        </div>

        <div className="mt-6 flex items-center gap-3 sm:gap-4">
          <button
            type="button"
            onClick={toggle}
            disabled={failed}
            aria-label={playing ? "Pause call recording" : "Play call recording"}
            className={cn(
              "grid size-14 shrink-0 place-items-center rounded-full bg-brand-cyan text-white shadow-soft transition-colors",
              "hover:bg-brand-cyan-strong focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-brand-cyan",
              "disabled:cursor-not-allowed disabled:opacity-50",
              playing && !reduced && "animate-pulse-ring",
            )}
          >
            {playing ? (
              <Pause className="size-6" fill="currentColor" aria-hidden="true" />
            ) : (
              <Play className="ml-0.5 size-6" fill="currentColor" aria-hidden="true" />
            )}
          </button>

          <div className="min-w-0 flex-1">
            <input
              type="range"
              min={0}
              max={duration}
              step={0.1}
              value={Math.min(time, duration)}
              onChange={onScrub}
              disabled={failed}
              aria-label="Seek"
              aria-valuetext={`${spokenTime(time)} of ${spokenTime(duration)}`}
              className={cn(
                "h-10 w-full cursor-pointer appearance-none bg-transparent disabled:cursor-not-allowed",
                "[&::-webkit-slider-runnable-track]:h-2 [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-[linear-gradient(to_right,var(--brand-cyan)_var(--pct),var(--line)_var(--pct))]",
                "[&::-webkit-slider-thumb]:-mt-1.5 [&::-webkit-slider-thumb]:size-5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-[3px] [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:bg-brand-cyan-strong [&::-webkit-slider-thumb]:shadow-soft",
                "[&::-moz-range-track]:h-2 [&::-moz-range-track]:rounded-full [&::-moz-range-track]:bg-line",
                "[&::-moz-range-progress]:h-2 [&::-moz-range-progress]:rounded-full [&::-moz-range-progress]:bg-brand-cyan",
                "[&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-[3px] [&::-moz-range-thumb]:border-white [&::-moz-range-thumb]:bg-brand-cyan-strong",
                "focus-visible:outline-none [&:focus-visible::-webkit-slider-thumb]:ring-4 [&:focus-visible::-webkit-slider-thumb]:ring-brand-cyan/35",
              )}
              style={{ "--pct": `${pct}%` } as CSSProperties}
            />
            <div className="-mt-1 flex justify-between text-xs font-bold text-brand-gray tabular-nums">
              <span>{formatTime(time)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={toggleMute}
            aria-pressed={muted}
            aria-label={muted ? "Unmute" : "Mute"}
            className="grid size-11 shrink-0 place-items-center rounded-full text-ink-soft ring-1 ring-line transition-colors hover:bg-surface-pale hover:text-ink focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan"
          >
            {muted ? <VolumeX className="size-5" aria-hidden="true" /> : <Volume2 className="size-5" aria-hidden="true" />}
          </button>
        </div>

        {failed ? (
          <p role="status" className="mt-4 rounded-2xl bg-surface-pale px-4 py-3 text-sm font-semibold text-ink">
            The recording could not be played here. The full transcript is beside the player.
          </p>
        ) : (
          <p className="mt-4 text-sm text-brand-gray">Tap any line of the transcript to jump to it.</p>
        )}
      </div>

      {/* Transcript */}
      <div className="rounded-[2rem] bg-surface-soft p-2 ring-1 ring-line">
        <div className="flex items-center justify-between gap-3 px-4 pt-1.5 pb-1">
          <p id="call-transcript-title" className="text-xs font-extrabold tracking-[0.14em] text-brand-gray uppercase">
            Transcript
          </p>
          {failed ? null : (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              aria-pressed={showAll}
              className="inline-flex min-h-10 items-center rounded-full px-2 text-xs font-bold text-brand-cyan-strong hover:underline focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan"
            >
              {showAll ? "Follow the call" : "Show full transcript"}
            </button>
          )}
        </div>
        {/* Fixed height: lines appear inside the box, so the page never shifts while it fills. */}
        <ol
          ref={listRef}
          aria-labelledby="call-transcript-title"
          className="relative flex h-[26rem] flex-col gap-1.5 overflow-y-auto overscroll-contain px-2 pb-3 [scrollbar-width:thin] sm:h-[30rem] sm:px-3"
        >
          {visibleCount === 0 && lines.length > 0 ? (
            <li className="flex flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
              <p className="text-sm font-bold text-brand-gray">Press play to follow the call</p>
              <button
                type="button"
                onClick={() => seek(lines[0].start, true)}
                aria-label={`Play from the start: ${lines[0].speaker} says ${lines[0].text}`}
                className="flex max-w-[88%] items-center gap-2 rounded-[1.15rem] rounded-bl-md bg-white px-3.5 py-2 text-left text-[0.95rem] leading-snug text-ink opacity-50 ring-1 ring-line transition-opacity hover:opacity-80 focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan"
              >
                <FoggyAvatar size={24} decorative />
                {lines[0].text}
              </button>
            </li>
          ) : null}
          {lines.slice(0, visibleCount).map((line, i) => {
            const foggy = line.speaker.toLowerCase() === "foggy";
            const active = i === current;
            const firstOfRun = i === 0 || lines[i - 1].speaker !== line.speaker;
            return (
              <li
                key={`${line.start}-${i}`}
                ref={(el) => {
                  lineRefs.current[i] = el;
                }}
                className={cn(
                  "flex flex-col",
                  foggy ? "items-start pl-9" : "items-end",
                  firstOfRun && i > 0 && "mt-2",
                  // Entrance as the line is reached: fade in and rise 4px.
                  !revealAll &&
                    "transition-[opacity,translate] duration-[180ms] ease-out starting:translate-y-1 starting:opacity-0 motion-reduce:transition-none",
                )}
              >
                {firstOfRun ? (
                  <span className={cn("mb-1 flex items-center gap-1.5 text-xs font-extrabold text-brand-gray", foggy && "-ml-9")}>
                    {foggy ? <FoggyAvatar size={28} decorative /> : null}
                    {line.speaker}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={() => seek(line.start, true)}
                  aria-current={active ? "true" : undefined}
                  aria-label={`${line.speaker} at ${formatTime(line.start)}: ${line.text}`}
                  className={cn(
                    "max-w-[88%] rounded-[1.15rem] px-3.5 py-2 text-left text-[0.95rem] leading-snug transition-[box-shadow,opacity,background-color] duration-200",
                    "focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan",
                    foggy ? "rounded-bl-md text-ink" : "rounded-br-md text-white",
                    foggy &&
                      (active
                        ? "bg-surface-pale shadow-soft ring-2 ring-brand-cyan"
                        : "bg-white ring-1 ring-line hover:bg-surface-pale"),
                    !foggy &&
                      (active
                        ? "bg-brand-cyan-strong shadow-soft ring-2 ring-brand-cyan-strong ring-offset-2 ring-offset-surface-soft"
                        : "bg-brand-cyan hover:bg-brand-cyan-strong"),
                    revealAll && started && current >= 0 && i > current && "opacity-60",
                  )}
                >
                  {line.text}
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
