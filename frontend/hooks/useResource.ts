"use client";

import { useCallback, useEffect, useState } from "react";

/** Fetch a resource, discard stale responses, and derive loading from request identity. */
export function useResource<T>(url: string | null, parse: (response: Response) => Promise<T>) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{
    url: string;
    revision: number;
    data?: T;
    error?: string;
  } | null>(null);

  useEffect(() => {
    if (!url) return;
    const controller = new AbortController();
    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Unable to load data (HTTP ${response.status}). Please try again.`);
        return parse(response);
      })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ url, revision, data });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setResult({ url, revision, error: error instanceof Error ? error.message : "Unable to load data." });
        }
      });
    return () => controller.abort();
  }, [url, revision, parse]);

  const current = result?.url === url && result.revision === revision;
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  return {
    data: current ? result.data : undefined,
    error: current ? result.error ?? null : null,
    loading: url !== null && !current,
    refresh,
  };
}
