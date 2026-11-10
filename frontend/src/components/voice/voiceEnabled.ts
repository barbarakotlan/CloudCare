/**
 * In-browser voice ("Talk to Foggy") is off unless NEXT_PUBLIC_VOICE_ENABLED is exactly "on".
 * Every voice session is billed by ElevenLabs, so the buttons that open it are hidden and the
 * voice SDK never loads while this is off. The voice code stays in place behind the flag.
 */
export const VOICE_ENABLED = process.env.NEXT_PUBLIC_VOICE_ENABLED === "on";
