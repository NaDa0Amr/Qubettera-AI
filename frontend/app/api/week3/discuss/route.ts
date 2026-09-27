import { NextRequest } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { DiscussRequest } from "@/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Long-running timeouts are handled by AbortSignal.timeout() alone.
//
// Do NOT pass a custom Undici `dispatcher` here. Node's built-in fetch
// already uses its own internal Undici; passing an `Agent` instance from
// the separately-installed `undici` package causes the fetch to throw
// "fetch failed" within milliseconds, before any network request is made.
//
// Safe without the dispatcher because:
//   1. Undici's `bodyTimeout` resets on every received chunk, not on total
//      duration. The Week 3 discussion stream emits SSE events continuously
//      as each token_chunk arrives, so `bodyTimeout` never fires even during
//      a long tool call with a 30–60s gap.
//   2. The total duration is capped by `AbortSignal.timeout(...)` below.
//   3. `headersTimeout` only covers the initial response headers; FastAPI
//      returns those immediately.
const LONG_RUNNING_TIMEOUT_MS = 90 * 60 * 1000; // 90 minutes

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

// Canned mock SSE sequence for development when MOCK_BACKEND=true.
// Emits a complete 2-agent, 1-initial + 1-discussion round sequence.
async function* mockStream(topic: string, discussionId: string): AsyncGenerator<string> {
  const agentIds = ["dr_aris", "prof_elena"];

  function event(name: string, data: unknown): string {
    return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
  }

  const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

  yield event("stream_started", { discussion_id: discussionId });
  await delay(200);

  yield event("discussion_started", {
    event: "discussion_started",
    discussion_id: discussionId,
    created_at: new Date().toISOString(),
    config: {
      brief: {
        objective: topic,
        constraints: ["One A100 GPU (40GB)", "3-month timeline"],
        topics: ["MoE vs Dense Layers", "SSM vs Attention"],
        strict_notes: ["Cite all evidence with exact source URLs."],
      },
      participant_ids: agentIds,
      num_rounds: 3,
      model_config: {},
    },
    graph: {
      directed: true,
      nodes: agentIds,
      edges: [["dr_aris", "prof_elena"], ["prof_elena", "dr_aris"]],
    },
  });
  await delay(400);

  const mockMessages = [
    {
      sender_id: "dr_aris",
      phase: "initial",
      round_number: 0,
      content:
        "### Initial Position\n\nI strongly recommend adopting **Mixture-of-Experts (MoE)** architecture. Production evidence from Mixtral and Switch Transformer demonstrates 3-5x inference efficiency gains at comparable quality. Given a single A100 constraint, MoE's conditional compute is not a luxury — it's a necessity.\n\n**Evidence**: [Switch Transformer (2022)](https://arxiv.org/abs/2101.03961)",
      opinion: "Strong pro-MoE stance based on production efficiency data.",
      retrieval_query: "MoE vs dense transformer inference cost A100",
      evidence: [
        {
          text: "Switch Transformer achieves 7x pre-training speedup over T5-XXL with comparable fine-tuning quality.",
          title: "Switch Transformers: Scaling to Trillion Parameter Models",
          url: "https://arxiv.org/abs/2101.03961",
          score: 0.38,
        },
      ],
    },
    {
      sender_id: "prof_elena",
      phase: "initial",
      round_number: 0,
      content:
        "### Initial Position\n\nThe theoretical stability guarantees for dense networks are simply more robust. MoE routing collapse is a real failure mode that has cost production teams weeks of debugging. I prefer **dense feed-forward** layers with sliding window attention to manage the context window under GPU constraints.\n\n**Reference**: [Routing in MoE: Stability Analysis (2023)](https://arxiv.org/abs/2308.09583)",
      opinion: "Pro-dense, skeptical of MoE routing stability.",
      retrieval_query: "MoE routing collapse instability dense transformer comparison",
      evidence: [
        {
          text: "Expert collapse in top-k routing can reduce effective model capacity by up to 40% without load-balancing auxiliary losses.",
          title: "On the Pitfalls of MoE Training",
          url: "https://arxiv.org/abs/2308.09583",
          score: 0.42,
        },
      ],
    },
    {
      sender_id: "dr_aris",
      phase: "discussion",
      round_number: 1,
      content:
        "### Round 1 Response\n\nProf. Vance raises a legitimate concern about routing collapse. However, modern load-balancing losses (auxiliary loss on expert utilization) have largely mitigated this in 2024-era implementations. I concede that naive implementations do fail — but best-practice MoE training with z-loss regularization is now standard.",
      opinion: "Still pro-MoE but acknowledging routing concerns with caveats.",
      retrieval_query: "MoE auxiliary loss load balancing z-loss 2024",
      evidence: [],
    },
    {
      sender_id: "prof_elena",
      phase: "discussion",
      round_number: 1,
      content:
        "### Round 1 Response\n\nAris's point about z-loss is well-taken. I am revising my position toward a **hybrid approach**: dense attention with MoE feed-forward layers in alternating blocks. This captures efficiency gains where MoE excels (FF layers) while retaining stability in attention.",
      opinion: "Moved toward hybrid architecture.",
      retrieval_query: "hybrid MoE dense attention interleaved transformer",
      evidence: [],
    },
  ];

  let seq = 1;
  for (const msg of mockMessages) {
    await delay(600);
    yield event("turn_completed", {
      event: "turn_completed",
      discussion_id: discussionId,
      created_at: new Date().toISOString(),
      message: {
        message_id: `${discussionId}:${String(seq).padStart(4, "0")}`,
        discussion_id: discussionId,
        sequence_number: seq++,
        recipient_ids: agentIds.filter((id) => id !== msg.sender_id),
        created_at: new Date().toISOString(),
        ...msg,
      },
      runtime_metadata: {},
    });
  }

  await delay(400);
  yield event("discussion_completed", {
    event: "discussion_completed",
    discussion_id: discussionId,
    created_at: new Date().toISOString(),
    message_count: mockMessages.length,
    discussion_turn_count: mockMessages.length,
  });
}

export async function POST(req: NextRequest): Promise<Response> {
  log.info("request_started", "POST /api/week3/discuss");

  let body: DiscussRequest;
  try {
    body = (await req.json()) as DiscussRequest;
  } catch {
    return new Response(
      JSON.stringify({ error: { code: "engine_error", message: "Invalid JSON body." } }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  if (serverEnv.mockBackend) {
    const discussionId = `mock-${Date.now()}`;
    log.info("sse_stream_started", "POST /api/week3/discuss (mock)", { discussion_id: discussionId });

    const encoder = new TextEncoder();
    const gen = mockStream(body.topic, discussionId);

    const stream = new ReadableStream({
      async pull(controller) {
        const { value, done } = await gen.next();
        if (done) {
          controller.close();
          return;
        }
        controller.enqueue(encoder.encode(value));
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Discussion-Id": discussionId,
      },
    });
  }

  const upstreamUrl = `${serverEnv.fastapiUrl}/week3/discuss`;
  log.info("request_started", `Fetching ${upstreamUrl}`, {
    upstream_url: upstreamUrl,
  });

  try {
    const upstream = await fetch(upstreamUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(LONG_RUNNING_TIMEOUT_MS),
      cache: "no-store",
    });

    if (!upstream.ok || !upstream.body) {
      log.error("request_failed", "POST /week3/discuss upstream failed", {
        status: upstream.status,
      });
      return new Response(
        JSON.stringify({ error: { code: "engine_error", message: "Upstream stream failed." } }),
        { status: upstream.status, headers: { "Content-Type": "application/json" } },
      );
    }

    const discussionId = upstream.headers.get("X-Discussion-Id") ?? "";
    log.info("sse_stream_started", "POST /api/week3/discuss (proxied)", { discussion_id: discussionId });

    // Pipe through a TransformStream for the same reasons as the analytics
    // route: the route handler returns immediately, and the pipe runs
    // decoupled from the handler's execution context lifetime. If the
    // upstream breaks mid-stream, we write a terminal `discussion_failed`
    // event so the client sees a clean SSE end rather than an incomplete
    // chunked body (ERR_INCOMPLETE_CHUNKED_ENCODING).
    const { readable, writable } = new TransformStream();
    const encoder = new TextEncoder();

    upstream.body.pipeTo(writable).catch((pipeErr) => {
      const writer = writable.getWriter();
      const errorEvent =
        `event: discussion_failed\ndata: ${JSON.stringify({
          code: "pipe_error",
          message: pipeErr instanceof Error ? pipeErr.message : "Upstream connection lost",
        })}\n\n`;
      writer
        .write(encoder.encode(errorEvent))
        .catch(() => {/* client already gone, nothing to do */})
        .finally(() => writer.close().catch(() => {}));

      log.warn("sse_pipe_error", "Discussion upstream pipe broke", {
        discussion_id: discussionId,
        error: describeFetchError(pipeErr),
      });
    });

    return new Response(readable, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Discussion-Id": discussionId,
      },
    });
  } catch (err) {
    log.error("request_failed", "POST /week3/discuss network error", {
      upstream_url: upstreamUrl,
      error: describeFetchError(err),
    });
    return new Response(
      JSON.stringify({ error: { code: "engine_error", message: "Network error reaching backend." } }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
}
