"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { parseSSEChunk } from "@/lib/sse";
import type {
  DiscussionStreamState,
  DiscussionStreamStatus,
  DiscussionMessage,
  ParticipantState,
  DiscussRequest,
  StreamStartedData,
  DiscussionStartedData,
  TurnCompletedData,
  TokenChunkData,
  DiscussionCompletedData,
  DiscussionFailedData,
  StreamingDraft,
} from "@/types";

// 4 minutes. Week 2 agents call retrieval tools between LLM generations, and
// a single Kaggle Ollama / Supabase round trip can take 30-60 seconds. The
// previous 90-second window was too tight: a slow tool call plus prompt
// assembly plus the initial LLM call routinely exceeded it and the frontend
// aborted the stream mid-discussion.
const INACTIVITY_TIMEOUT_MS = 240_000;
const MAX_RETRIES = 3;

const INITIAL_STATE: DiscussionStreamState = {
  status: "idle",
  discussionId: null,
  brief: null,
  graph: null,
  config: null,
  messages: [],
  participants: {},
  error: null,
  lastEventAt: null,
  streamingMessages: {},
};

function buildParticipants(ids: string[]): Record<string, ParticipantState> {
  const out: Record<string, ParticipantState> = {};
  for (const id of ids) {
    out[id] = { id, status: "idle" };
  }
  return out;
}

/**
 * Pure reducer for non-token events.
 * token_chunk is handled separately in handleTokenChunk because it uses
 * refs + requestAnimationFrame instead of going through setState per token.
 */
function applyEvent(
  prev: DiscussionStreamState,
  eventName: string,
  data: unknown,
): DiscussionStreamState {
  if (eventName === "stream_started") {
    const d = data as StreamStartedData;
    return { ...prev, discussionId: d.discussion_id, lastEventAt: Date.now() };
  }

  if (eventName === "discussion_started") {
    const d = data as DiscussionStartedData;
    return {
      ...prev,
      brief: d.config.brief,
      graph: d.graph,
      config: d.config,
      participants: buildParticipants(d.config.participant_ids),
      lastEventAt: Date.now(),
    };
  }

  if (eventName === "turn_completed") {
    const d = data as TurnCompletedData;
    const msg: DiscussionMessage = d.message;

    const updatedParticipants = { ...prev.participants };
    // Other agents may still be generating in parallel.
    updatedParticipants[msg.sender_id] = { id: msg.sender_id, status: "spoke" };

    return {
      ...prev,
      messages: [...prev.messages, msg],
      participants: updatedParticipants,
      lastEventAt: Date.now(),
    };
  }

  if (eventName === "discussion_completed") {
    const d = data as DiscussionCompletedData;
    const finalParticipants = { ...prev.participants };
    for (const id of Object.keys(finalParticipants)) {
      if (finalParticipants[id].status !== "errored") {
        finalParticipants[id] = { id, status: "spoke" };
      }
    }
    return {
      ...prev,
      status: "done" as DiscussionStreamStatus,
      discussionId: d.discussion_id,
      participants: finalParticipants,
      lastEventAt: Date.now(),
    };
  }

  if (eventName === "discussion_failed") {
    const d = data as DiscussionFailedData;
    return {
      ...prev,
      status: "error" as DiscussionStreamStatus,
      error: d.error,
      lastEventAt: Date.now(),
    };
  }

  return prev;
}

export function useStreamingDiscussion() {
  const [state, setState] = useState<DiscussionStreamState>(INITIAL_STATE);

  const abortRef = useRef<AbortController | null>(null);
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  // Keep separate drafts for parallel agents. Flush to React at most once per
  // animation frame, even when many tokens arrive in the same frame.
  const streamingBufferRef = useRef<Record<string, StreamingDraft>>({});
  const rafRef = useRef<number | null>(null);

  const cancelPendingRaf = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  // Cancel a pending rAF if the hook unmounts mid-stream.
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  const resetInactivityTimer = useCallback((abort: AbortController) => {
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    inactivityTimerRef.current = setTimeout(() => {
      abort.abort();
      setState((prev) => ({
        ...prev,
        status: "error",
        error:
          "No events received for 4 minutes. The stream timed out. " +
          "This usually means an agent's retrieval call is taking longer than expected.",
      }));
    }, INACTIVITY_TIMEOUT_MS);
  }, []);

  /**
   * Append this model run's text to its agent's draft. A new model run replaces
   * earlier internal output, such as a tool decision before the final answer.
   */
  const handleTokenChunk = useCallback((d: TokenChunkData) => {
    if (!d.agent_id) return;
    const id = d.agent_id;
    const previous = streamingBufferRef.current[id];
    streamingBufferRef.current[id] = {
      text: (previous?.runId === d.run_id ? previous.text : "") + d.token,
      round: d.round,
      runId: d.run_id,
    };

    if (!previous) {
      setState((prev) => {
        if (!prev.participants[id]) return prev;
        return {
          ...prev,
          participants: {
            ...prev.participants,
            [id]: { id, status: "speaking" },
          },
        };
      });
    }

    // Schedule a single state flush per frame.
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        setState((prev) => ({
          ...prev,
          streamingMessages: { ...streamingBufferRef.current },
          lastEventAt: Date.now(),
        }));
      });
    }
  }, []);

  const handleEvent = useCallback(
    (eventName: string, data: unknown) => {
      // token_chunk bypasses setState entirely — handled via refs + rAF.
      if (eventName === "token_chunk") {
        handleTokenChunk(data as TokenChunkData);
        return;
      }

      if (eventName === "turn_completed") {
        const completed = data as TurnCompletedData;
        delete streamingBufferRef.current[completed.message.sender_id];
        cancelPendingRaf();
      } else if (eventName === "discussion_completed" || eventName === "discussion_failed") {
        streamingBufferRef.current = {};
        cancelPendingRaf();
      }

      setState((prev) => ({
        ...applyEvent(prev, eventName, data),
        streamingMessages: { ...streamingBufferRef.current },
      }));
    },
    [handleTokenChunk, cancelPendingRaf],
  );

  const startDiscussion = useCallback(
    async (request: DiscussRequest) => {
      // Cancel any existing stream and clear pending stream state.
      abortRef.current?.abort();
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      cancelPendingRaf();
      streamingBufferRef.current = {};
      retryCountRef.current = 0;

      setState({ ...INITIAL_STATE, status: "streaming" });

      const attempt = async () => {
        const abort = new AbortController();
        abortRef.current = abort;

        let buffer = "";

        try {
          const res = await fetch("/api/week3/discuss", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(request),
            signal: abort.signal,
          });

          if (!res.ok || !res.body) {
            throw new Error(`HTTP ${res.status}: stream unavailable`);
          }

          resetInactivityTimer(abort);

          const reader = res.body.getReader();
          const decoder = new TextDecoder();

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const { events, remaining } = parseSSEChunk(chunk, buffer);
            buffer = remaining;

            resetInactivityTimer(abort);

            for (const ev of events) {
              handleEvent(ev.event, ev.data);
            }
          }

          // Stream ended without discussion_completed — flag as error.
          setState((prev) => {
            if (prev.status === "streaming") {
              return {
                ...prev,
                status: "error",
                error: "Stream ended unexpectedly.",
              };
            }
            return prev;
          });
        } catch (err: unknown) {
          if ((err as { name?: string }).name === "AbortError") return;

          const message =
            err instanceof Error ? err.message : "Stream connection failed.";

          if (retryCountRef.current < MAX_RETRIES) {
            retryCountRef.current++;
            const delay = Math.pow(2, retryCountRef.current - 1) * 1000;
            console.warn(
              `[useStreamingDiscussion] Retry ${retryCountRef.current}/${MAX_RETRIES} in ${delay}ms`,
            );
            setTimeout(() => {
              void attempt();
            }, delay);
          } else {
            setState((prev) => ({
              ...prev,
              status: "error",
              error: `Connection failed after ${MAX_RETRIES} retries: ${message}`,
            }));
          }
        } finally {
          if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
        }
      };

      void attempt();
    },
    [resetInactivityTimer, handleEvent, cancelPendingRaf],
  );

  const stopDiscussion = useCallback(() => {
    abortRef.current?.abort();
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    cancelPendingRaf();
    streamingBufferRef.current = {};
    setState((prev) => ({ ...prev, status: "idle", streamingMessages: {} }));
  }, [cancelPendingRaf]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    cancelPendingRaf();
    streamingBufferRef.current = {};
    setState(INITIAL_STATE);
  }, [cancelPendingRaf]);

  return { state, startDiscussion, stopDiscussion, reset };
}
