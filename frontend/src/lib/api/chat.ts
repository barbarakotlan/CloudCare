import { apiFetch } from "./client";
import type { ChatMessageOut, ChatReply } from "./types";

export const sendChat = (message: string) => apiFetch<ChatReply>("/chat", { method: "POST", body: { message } });

/** Oldest first. Patients omit `patientId`; clinicians must pass it. */
export const getChatHistory = (patientId?: string, signal?: AbortSignal) =>
  apiFetch<ChatMessageOut[]>(
    patientId ? `/chat/history?patient_id=${encodeURIComponent(patientId)}` : "/chat/history",
    { signal },
  );
