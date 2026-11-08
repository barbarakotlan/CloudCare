import { ApiError, apiFetch } from "./client";
import type { ChatCapabilities, ChatIn, ChatMessageOut, ChatReply } from "./types";

export const sendChat = (message: string) =>
  apiFetch<ChatReply>("/chat", { method: "POST", body: { message, source: "chat" } satisfies ChatIn });

/** Oldest first. Patients omit `patientId`; clinicians must pass it. */
export const getChatHistory = (patientId?: string, signal?: AbortSignal) =>
  apiFetch<ChatMessageOut[]>(
    patientId ? `/chat/history?patient_id=${encodeURIComponent(patientId)}` : "/chat/history",
    { signal },
  );

/** What the backend says it can really do. Older backends without the route can only queue messages. */
export const DEFAULT_CHAT_CAPABILITIES: ChatCapabilities = {
  message_care_team: true,
  call_care_team: false,
  emergency_call_assist: false,
  simulated: false,
};

export async function getChatCapabilities(signal?: AbortSignal): Promise<ChatCapabilities> {
  try {
    const caps = await apiFetch<Partial<ChatCapabilities>>("/chat/capabilities", { signal });
    return { ...DEFAULT_CHAT_CAPABILITIES, ...caps };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 405)) return DEFAULT_CHAT_CAPABILITIES;
    throw err;
  }
}
