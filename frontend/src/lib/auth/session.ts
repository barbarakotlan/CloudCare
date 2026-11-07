/**
 * Session storage shared by every auth provider.
 * localStorage keys: `cloudcare.token` (bearer token), `cloudcare.user` (user JSON).
 * Components subscribe via useSession() (useSyncExternalStore).
 */
import type { Role } from "@/lib/api/types";

export const TOKEN_KEY = "cloudcare.token";
export const USER_KEY = "cloudcare.user";

export type SessionUser = { id: string; full_name: string; role: Role; email?: string };
export type Session = { token: string; user: SessionUser };

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === TOKEN_KEY || e.key === USER_KEY || e.key === null) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * Raw snapshot string ("token\nuserJSON") so useSyncExternalStore gets a
 * stable primitive between calls. "" means signed out.
 */
export function sessionSnapshot(): string {
  const s = storage();
  if (!s) return "";
  const token = s.getItem(TOKEN_KEY);
  const user = s.getItem(USER_KEY);
  return token && user ? `${token}\n${user}` : "";
}

export function parseSnapshot(snapshot: string): Session | null {
  if (!snapshot) return null;
  const idx = snapshot.indexOf("\n");
  if (idx < 0) return null;
  try {
    const user = JSON.parse(snapshot.slice(idx + 1)) as SessionUser;
    if (!user || (user.role !== "patient" && user.role !== "clinician")) return null;
    return { token: snapshot.slice(0, idx), user };
  } catch {
    return null;
  }
}

export function readSession(): Session | null {
  return parseSnapshot(sessionSnapshot());
}

export function writeSession(session: Session) {
  const s = storage();
  if (!s) return;
  s.setItem(TOKEN_KEY, session.token);
  s.setItem(USER_KEY, JSON.stringify(session.user));
  emit();
}

export function clearSession() {
  const s = storage();
  if (!s) return;
  s.removeItem(TOKEN_KEY);
  s.removeItem(USER_KEY);
  emit();
}

export function getToken(): string | null {
  return storage()?.getItem(TOKEN_KEY) ?? null;
}

/** Called by the API client on a 401: the token is stale, so drop it. */
export function handleUnauthorized() {
  clearSession();
}
