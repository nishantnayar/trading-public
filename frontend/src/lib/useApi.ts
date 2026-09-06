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
  const [result, setResult] = useState<{
    path: string;
    data: T | null;
    error: string | null;
  } | null>(null);

  useEffect(() => {
    if (!path) {
      return;
    }

    const controller = new AbortController();

    apiGet<T>(path, controller.signal)
      .then((value) => {
        setResult({ path, data: value, error: null });
      })
      .catch((err: unknown) => {
        // An abort is a deliberate cancellation, not a failure: leave state untouched
        // so the replacement request owns it.
        if (controller.signal.aborted) return;
        setResult({
          path,
          data: null,
          error: err instanceof Error ? err.message : String(err),
        });
      });

    return () => controller.abort();
  }, [path]);

  if (!path) {
    return { data: null, error: null, loading: false };
  }

  const matched = result !== null && result.path === path;
  return {
    data: matched ? result.data : null,
    error: matched ? result.error : null,
    loading: !matched,
  };
}
