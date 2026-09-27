import { NextRequest } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { AnalyticsPayload, MetricName } from "@/types";
import mockAnalytics from "@/lib/mocks/analytics.json";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const METRICS_ORDER: MetricName[] = [
  "opinion_change",
  "agreement",
  "influence",
  "sentiment",
  "report",
  "visuals",
];

// Long-running timeouts are handled by AbortSignal.timeout() alone.
//
// Do NOT pass a custom Undici `dispatcher` here. Node's built-in fetch
// already uses its own internal Undici; passing an `Agent` instance from
// the separately-installed `undici` package causes the fetch to throw
// "fetch failed" within milliseconds, before any network request is made.
//
// This is safe without the dispatcher because:
//   1. Undici's `bodyTimeout` resets on every received chunk, not on total
//      duration. The backend emits an SSE keep-alive comment every 15s
//      during long analytics runs, so `bodyTimeout` never fires.
//   2. The total duration is capped by `AbortSignal.timeout(...)` below.
//   3. `headersTimeout` only covers the initial response headers; FastAPI
//      returns those immediately.
const LONG_RUNNING_TIMEOUT_MS = 90 * 60 * 1000; // 90 minutes

// Synthesize a progressive SSE stream from a completed analytics JSON payload.
// Used when the backend /week4/analytics/{id}/stream endpoint is not yet available.
async function* syntheticAnalyticsStream(
  payload: AnalyticsPayload,
  discussionId: string,
): AsyncGenerator<string> {
  function event(name: string, data: unknown): string {
    return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
  }

  const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

  yield event("analytics_started", {
    discussion_id: discussionId,
    metrics_planned: METRICS_ORDER,
  });

  for (const metric of METRICS_ORDER) {
    yield event("metric_started", { metric, started_at: new Date().toISOString() });
    await delay(300);

    let data: unknown;
    if (metric === "opinion_change") data = payload.opinion_change;
    else if (metric === "agreement") data = payload.agreement;
    else if (metric === "influence") data = payload.influence;
    else if (metric === "sentiment") data = payload.sentiment;
    else if (metric === "report") data = { markdown: "# Report\n\nReport not available in synthetic mode." };
    else if (metric === "visuals") data = { opinion_trajectory_url: null, interaction_graph_url: null };
    else data = null;

    yield event("metric_completed", { metric, duration_ms: 300, data });
    await delay(200);
  }

  yield event("analytics_completed", {
    discussion_id: discussionId,
    total_duration_ms: METRICS_ORDER.length * 500,
  });
}

/**
 * Unwrap the real cause of a fetch failure for logging. Node's fetch wraps
 * network errors in a generic TypeError with `message === "fetch failed"`
 * and the real error (ECONNREFUSED, ENOTFOUND, etc.) on `.cause`. Logging
 * only `.message` hides the actual problem.
 */
function describeFetchError(err: unknown): string {
  if (!(err instanceof Error)) return String(err);
  const cause = (err as { cause?: unknown }).cause;
  if (cause instanceof Error) {
    return `${err.message} (cause: ${cause.name}: ${cause.message})`;
  }
  if (cause !== undefined) {
    return `${err.message} (cause: ${String(cause)})`;
  }
  return err.message;
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params;
  log.info("request_started", "GET /api/week4/analytics/[id]/stream", { discussion_id: id });

  const encoder = new TextEncoder();

  // Mock mode or mock discussion: synthesize from static analytics fixture.
  if (serverEnv.mockBackend || id === "mock-discussion-001") {
    const gen = syntheticAnalyticsStream(mockAnalytics as unknown as AnalyticsPayload, id);
    const stream = new ReadableStream({
      async pull(controller) {
        const { value, done } = await gen.next();
        if (done) { controller.close(); return; }
        controller.enqueue(encoder.encode(value));
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  const upstreamUrl = `${serverEnv.fastapiUrl}/week4/analytics/${id}/stream`;
  log.info("request_started", `Fetching ${upstreamUrl}`, {
    discussion_id: id,
    upstream_url: upstreamUrl,
  });

  try {
    const upstream = await fetch(upstreamUrl, {
      signal: AbortSignal.timeout(LONG_RUNNING_TIMEOUT_MS),
      cache: "no-store",
    });

    if (upstream.ok && upstream.body) {
      log.info("sse_stream_started", "GET /api/week4/analytics/[id]/stream (proxied)", { discussion_id: id });

      const { readable, writable } = new TransformStream();

      upstream.body.pipeTo(writable).catch((pipeErr) => {
        // The upstream (FastAPI) dropped the connection unexpectedly. The
        // Response was already committed as 200 chunked, so we can't change
        // the status code — write a terminal analytics_failed SSE event so
        // the client receives a clean stream end rather than an incomplete
        // chunked body (ERR_INCOMPLETE_CHUNKED_ENCODING).
        const writer = writable.getWriter();
        const errorEvent =
          `event: analytics_failed\ndata: ${JSON.stringify({
            code: "pipe_error",
            message: pipeErr instanceof Error ? pipeErr.message : "Upstream connection lost",
          })}\n\n`;
        writer
          .write(encoder.encode(errorEvent))
          .catch(() => {/* client already gone, nothing to do */})
          .finally(() => writer.close().catch(() => {}));

        log.warn("sse_pipe_error", "Upstream pipe broke mid-stream", {
          discussion_id: id,
          error: describeFetchError(pipeErr),
        });
      });

      return new Response(readable, {
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
          "X-Accel-Buffering": "no",
        },
      });
    }

    log.warn("request_failed", "Backend stream endpoint returned non-OK", {
      discussion_id: id,
      status: upstream.status,
    });
  } catch (err) {
    // Stream endpoint unreachable — fall through to polling fallback.
    // Log the full cause so the next failure is diagnosable.
    log.warn("request_failed", "Backend stream endpoint unavailable, falling back to polling", {
      discussion_id: id,
      upstream_url: upstreamUrl,
      error: describeFetchError(err),
    });
  }

  // Polling fallback: fetch the blocking JSON endpoint and synthesize metric events.
  const jsonUrl = `${serverEnv.fastapiUrl}/week4/analytics/${id}`;
  try {
    const jsonRes = await fetch(jsonUrl, {
      signal: AbortSignal.timeout(LONG_RUNNING_TIMEOUT_MS),
      cache: "no-store",
    });

    if (!jsonRes.ok) {
      return new Response(
        `event: analytics_failed\ndata: ${JSON.stringify({ code: "analytics_not_ready", message: `Backend returned ${jsonRes.status}` })}\n\n`,
        {
          headers: {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            Connection: "keep-alive",
            "X-Accel-Buffering": "no",
          },
        },
      );
    }

    const payload = (await jsonRes.json()) as AnalyticsPayload;
    const gen = syntheticAnalyticsStream(payload, id);

    const stream = new ReadableStream({
      async pull(controller) {
        const { value, done } = await gen.next();
        if (done) { controller.close(); return; }
        controller.enqueue(encoder.encode(value));
      },
    });

    log.info("sse_stream_started", "GET /api/week4/analytics/[id]/stream (synthetic from JSON)", { discussion_id: id });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    log.error("request_failed", "GET /api/week4/analytics/[id]/stream error", {
      discussion_id: id,
      upstream_url: jsonUrl,
      error: describeFetchError(err),
    });
    return new Response(
      `event: analytics_failed\ndata: ${JSON.stringify({ code: "engine_error", message: "Network error" })}\n\n`,
      {
        status: 502,
        headers: { "Content-Type": "text/event-stream; charset=utf-8" },
      },
    );
  }
}