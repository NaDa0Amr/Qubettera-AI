import { NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { DiscussionSummary } from "@/types";

export const dynamic = "force-dynamic";

const MOCK_DISCUSSIONS_LIST: DiscussionSummary[] = [
  {
    discussion_id: "mock-discussion-001",
    topic: "MoE vs Dense Layers for a 1B Parameter Transformer",
    created_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    num_rounds: 3,
    num_agents: 4,
    status: "completed",
    has_analytics: true,
  },
];

export async function GET(): Promise<NextResponse> {
  log.info("request_started", "GET /api/discussions");

  if (serverEnv.mockBackend) {
    log.info("request_completed", "GET /api/discussions (mock)", { source: "mock" });
    return NextResponse.json({ discussions: MOCK_DISCUSSIONS_LIST });
  }

  try {
    const upstream = await fetch(`${serverEnv.fastapiUrl}/discussions`, {
      signal: AbortSignal.timeout(10_000),
    });

    if (!upstream.ok) {
      log.warn("request_failed", "GET /discussions upstream failed, falling back to mock", {
        status: upstream.status,
      });
      return NextResponse.json({ discussions: MOCK_DISCUSSIONS_LIST });
    }

    const raw = await upstream.json();
    // FastAPI returns a flat DiscussionSummary[] array. Normalize into the
    // { discussions: [] } shape the frontend types / hooks expect uniformly.
    const discussions: DiscussionSummary[] = Array.isArray(raw)
      ? (raw as DiscussionSummary[])
      : ((raw as { discussions: DiscussionSummary[] }).discussions ?? []);
    log.info("request_completed", "GET /api/discussions", { count: discussions.length });
    return NextResponse.json({ discussions });
  } catch (err) {
    log.error("request_failed", "GET /api/discussions fetch error, falling back to mock", {
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json({ discussions: MOCK_DISCUSSIONS_LIST });
  }
}
