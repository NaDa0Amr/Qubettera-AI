"use client";

import { useState, useEffect, useRef } from "react";
import type { DiscussionSummary } from "@/types";

interface UseDiscussionHistoryResult {
  discussions: DiscussionSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDiscussionHistory(): UseDiscussionHistoryResult {
  const [discussions, setDiscussions] = useState<DiscussionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch("/api/discussions")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<{ discussions: DiscussionSummary[] }>;
      })
      .then((data) => {
        if (!cancelled) {
          setDiscussions(data.discussions);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load history.");
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [tick]);

  return {
    discussions,
    loading,
    error,
    refresh: () => setTick((t) => t + 1),
  };
}

/**
 * Extends useDiscussionHistory with automatic refresh when `streamStatus`
 * transitions into a terminal state ("done" | "error").  Mount this wherever
 * the history list is shown while a discussion may be running in the background.
 *
 * Usage in HistoryTab:
 *   const { discussions, loading, error, refresh } =
 *     useAutoRefreshDiscussionHistory(state.status);
 */
export function useAutoRefreshDiscussionHistory(
  streamStatus: string,
): UseDiscussionHistoryResult {
  const result = useDiscussionHistory();
  const prevStatusRef = useRef(streamStatus);

  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = streamStatus;

    // Refresh the list when the stream transitions from "streaming" → done/error,
    // so the newly-completed discussion appears without a manual button click.
    // Small delay gives the backend time to flush the final JSONL event to disk.
    if (prev === "streaming" && (streamStatus === "done" || streamStatus === "error")) {
      const t = setTimeout(() => result.refresh(), 1_500);
      return () => clearTimeout(t);
    }
  }, [streamStatus, result]);

  return result;
}
