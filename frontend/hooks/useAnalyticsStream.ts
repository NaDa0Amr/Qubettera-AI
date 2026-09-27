"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { parseSSEChunk } from "@/lib/sse";
import type {
  AnalyticsState,
  MetricName,
  MetricStatus,
} from "@/types";

const ALL_METRICS: MetricName[] = [
  "opinion_change",
  "agreement",
  "influence",
  "sentiment",
  "report",
  "visuals",
];

function buildInitialMetrics(): Record<MetricName, MetricStatus> {
  const m = {} as Record<MetricName, MetricStatus>;
  for (const name of ALL_METRICS) {
    m[name] = { state: "pending" };
  }
  return m;
}

const INITIAL_STATE: AnalyticsState = {
  discussionId: null,
  streamStatus: "idle",
  progress: { completed: 0, total: 0 },
  metrics: buildInitialMetrics(),
  error: null,
};

export function useAnalyticsStream(discussionId: string | null) {
  const [state, setState] = useState<AnalyticsState>({
    ...INITIAL_STATE,
    discussionId,
  });

  const abortRef = useRef<AbortController | null>(null);
  // Generation counter: incremented on every effect invocation. Lets the
  // async IIFE detect that it has been superseded (e.g. by React StrictMode's
  // intentional double-mount in development) and bail out without touching
  // state. Without this, StrictMode's mount→unmount→remount fires two
  // concurrent fetch requests to the stream endpoint and both race to write
  // the same React state.
  const generationRef = useRef(0);

  const retryMetric = useCallback((metricName: MetricName) => {
    setState((prev) => ({
      ...prev,
      metrics: {
        ...prev.metrics,
        [metricName]: { state: "pending" },
      },
    }));
  }, []);

  useEffect(() => {
    if (!discussionId) return;

    let buffer = "";
    const abort = new AbortController();
    abortRef.current = abort;
    const generation = ++generationRef.current;

    setState({
      ...INITIAL_STATE,
      discussionId,
      streamStatus: "streaming",
      metrics: buildInitialMetrics(),
    });

    (async () => {
      try {
        const res = await fetch(`/api/week4/analytics/${discussionId}/stream`, {
          signal: abort.signal,
        });

        // If a newer effect invocation has superseded us (StrictMode remount,
        // discussionId change), silently abandon — the new invocation owns the stream.
        if (generation !== generationRef.current) return;

        if (!res.ok || !res.body) {
          setState((prev) => ({
            ...prev,
            streamStatus: "failed",
            error: `HTTP ${res.status}`,
          }));
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          // Check generation before each state update.
          if (generation !== generationRef.current) return;

          const chunk = decoder.decode(value, { stream: true });
          const { events, remaining } = parseSSEChunk(chunk, buffer);
          buffer = remaining;

          for (const ev of events) {
            setState((prev) => applyEvent(prev, ev.event, ev.data));
          }
        }

        if (generation !== generationRef.current) return;

        // Stream ended — if not yet completed, mark as completed.
        setState((prev) => {
          if (prev.streamStatus === "streaming") {
            return { ...prev, streamStatus: "completed" };
          }
          return prev;
        });
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "AbortError") return;
        if (generation !== generationRef.current) return;
        setState((prev) => ({
          ...prev,
          streamStatus: "failed",
          error: err instanceof Error ? err.message : "Analytics stream failed.",
        }));
      }
    })();

    return () => {
      abort.abort();
    };
  }, [discussionId]);

  return { state, retryMetric };
}

function applyEvent(
  prev: AnalyticsState,
  eventName: string,
  data: unknown,
): AnalyticsState {
  // "stream_started" is emitted by the real FastAPI backend to confirm the
  // SSE connection is live. "analytics_started" is the synthetic frontend
  // fallback event. Both kick off the same state transition.
  if (eventName === "stream_started") {
    const d = data as { discussion_id?: string };
    return {
      ...prev,
      discussionId: d.discussion_id ?? prev.discussionId,
      streamStatus: "streaming",
      // Real backend doesn't emit metrics_planned up front — use the known 6.
      progress: { completed: 0, total: ALL_METRICS.length },
    };
  }

  if (eventName === "analytics_started") {
    const d = data as { discussion_id: string; metrics_planned: string[] };
    return {
      ...prev,
      discussionId: d.discussion_id,
      streamStatus: "streaming",
      progress: { completed: 0, total: d.metrics_planned.length },
    };
  }

  if (eventName === "metric_started") {
    const d = data as { metric: MetricName };
    return {
      ...prev,
      metrics: {
        ...prev.metrics,
        [d.metric]: { state: "running" },
      },
    };
  }

  if (eventName === "metric_completed") {
    const d = data as { metric: MetricName; duration_ms: number; data: unknown };
    return {
      ...prev,
      progress: {
        ...prev.progress,
        completed: prev.progress.completed + 1,
      },
      metrics: {
        ...prev.metrics,
        [d.metric]: {
          state: "ready",
          data: d.data,
          durationMs: d.duration_ms,
        },
      },
    };
  }

  if (eventName === "metric_failed") {
    // Backend sends { metric, error: string }.
    // Future-aligned shape sends { metric, code, message }.
    // Accept both to avoid silently swallowing the error text.
    const d = data as { metric: MetricName; code?: string; message?: string; error?: string };
    return {
      ...prev,
      metrics: {
        ...prev.metrics,
        [d.metric]: {
          state: "failed",
          code: d.code ?? "metric_error",
          message: d.message ?? d.error ?? "Unknown metric error",
        },
      },
    };
  }

  if (eventName === "analytics_completed") {
    return { ...prev, streamStatus: "completed" };
  }

  if (eventName === "analytics_failed") {
    // Backend sends { discussion_id, error: string }.
    // Future-aligned shape sends { code, message }.
    const d = data as { code?: string; message?: string; error?: string };
    return { ...prev, streamStatus: "failed", error: d.message ?? d.error ?? "Analytics failed" };
  }

  return prev;
}
