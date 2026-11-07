"use client";

import { useMemo, useSyncExternalStore } from "react";
import { parseSnapshot, sessionSnapshot, subscribeSession, type Session } from "./session";

const SERVER_SNAPSHOT = "\u0000server";

/**
 * Current session from localStorage.
 * Returns `undefined` while unknown (server render / hydration), `null` when signed out.
 */
export function useSession(): Session | null | undefined {
  const snapshot = useSyncExternalStore(subscribeSession, sessionSnapshot, () => SERVER_SNAPSHOT);
  return useMemo(() => (snapshot === SERVER_SNAPSHOT ? undefined : parseSnapshot(snapshot)), [snapshot]);
}
