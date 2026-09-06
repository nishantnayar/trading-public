"use client";

import { useEffect, useState } from "react";

import { apiGet } from "./api";

/**
 * Fetch `path` from the API, tracking loading and error state.
 *
 * The request is tied to an AbortController so that when `path` changes the in-flight
 * request is cancelled rather than merely ignored. Without this, two requests can race
 * and the slower — older — response wins, leaving the panel showing data for the
 * previous symbol.
 */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);

    apiGet<T>(path, controller.signal)
      .then((value) => {
        setData(value);
        setError(null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        // An abort is a deliberate cancellation, not a failure: leave state untouched
        // so the replacement request owns it.
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => controller.abort();
  }, [path]);

  return { data, error, loading };
}
