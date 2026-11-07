"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/api/client";

type AsyncState<T> = { data: T | undefined; error: string | null; loading: boolean };

/**
 * Loads data on mount (and whenever `key` changes). `reload()` refetches,
 * `setData` lets callers apply optimistic updates.
 */
export function useAsync<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>({ data: undefined, error: null, loading: key !== null });
  const [version, setVersion] = useState(0);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    if (key === null) return;
    const ctrl = new AbortController();
    fetcherRef.current(ctrl.signal).then(
      (data) => {
        if (!ctrl.signal.aborted) setState({ data, error: null, loading: false });
      },
      (err: unknown) => {
        if (ctrl.signal.aborted) return;
        setState((s) => ({ ...s, error: errorMessage(err), loading: false }));
      },
    );
    return () => ctrl.abort();
  }, [key, version]);

  const reload = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    setVersion((v) => v + 1);
  }, []);

  const setData = useCallback((updater: (prev: T | undefined) => T) => {
    setState((s) => ({ ...s, data: updater(s.data) }));
  }, []);

  return { ...state, reload, setData };
}
