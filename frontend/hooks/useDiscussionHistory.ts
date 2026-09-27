"use client";

import { useEffect, useRef } from "react";
import { useResource } from "@/hooks/useResource";
import type { DiscussionSummary } from "@/types";

interface UseDiscussionHistoryResult {
  discussions: DiscussionSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

async function parseDiscussions(response: Response): Promise<DiscussionSummary[]> {
  const data = await response.json();
  return data.discussions;
}

export function useDiscussionHistory(): UseDiscussionHistoryResult {
  const { data, ...state } = useResource("/api/discussions", parseDiscussions);
  return { discussions: data ?? [], ...state };
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
  const { refresh } = result;

  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = streamStatus;

    // Refresh the list when the stream transitions from "streaming" → done/error,
    // so the newly-completed discussion appears without a manual button click.
    // Small delay gives the backend time to flush the final JSONL event to disk.
    if (prev === "streaming" && (streamStatus === "done" || streamStatus === "error")) {
      const t = setTimeout(() => refresh(), 1_500);
      return () => clearTimeout(t);
    }
  }, [streamStatus, refresh]);

  return result;
}
