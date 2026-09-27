import { NextRequest, NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { AnalyticsPayload } from "@/types";
import mockAnalytics from "@/lib/mocks/analytics.json";

export const dynamic = "force-dynamic";

// In-memory cache: discussionId -> { data, timestamp }
// A Map is sufficient for a single-instance deployment; use Redis for multi-replica.
const analyticsCache = new Map<
  string,
  { data: AnalyticsPayload; timestamp: number }
>();

const CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  const refresh = req.nextUrl.searchParams.get("refresh") === "true";

  log.info("request_started", "GET /api/week4/analytics/[id]", { discussion_id: id, refresh });

  if (serverEnv.mockBackend || id === "mock-discussion-001") {
    log.info("request_completed", "GET /api/week4/analytics/[id] (mock)", { discussion_id: id });
    return NextResponse.json(mockAnalytics as unknown as AnalyticsPayload);
  }

  // Check cache unless refresh was requested.
  if (!refresh) {
    const cached = analyticsCache.get(id);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
      log.info("request_completed", "GET /api/week4/analytics/[id] (cache hit)", { discussion_id: id });
      return NextResponse.json(cached.data);
    }
  }

  try {
    const url = new URL(`${serverEnv.fastapiUrl}/week4/analytics/${id}`);
    if (refresh) url.searchParams.set("refresh", "true");

    const upstream = await fetch(url.toString(), {
      // Analytics can take 30-90 seconds on first call.
      signal: AbortSignal.timeout(120_000),
    });

    if (!upstream.ok) {
      const code = upstream.status === 404 ? "discussion_not_found" : "analytics_not_ready";
      log.warn("request_failed", "GET /week4/analytics/{id} upstream failed", {
        status: upstream.status,
        discussion_id: id,
      });
      return NextResponse.json(
        { error: { code, message: `Upstream returned ${upstream.status}` } },
        { status: upstream.status },
      );
    }

    const data = (await upstream.json()) as AnalyticsPayload;

    // Store in cache.
    analyticsCache.set(id, { data, timestamp: Date.now() });

    log.info("request_completed", "GET /api/week4/analytics/[id]", { discussion_id: id });
    return NextResponse.json(data);
  } catch (err) {
    log.error("request_failed", "GET /api/week4/analytics/[id] error", {
      discussion_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: { code: "engine_error", message: "Network error reaching backend." } },
      { status: 502 },
    );
  }
}
