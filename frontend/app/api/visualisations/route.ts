import { NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * GET /api/visualisations
 *
 * Proxies GET /visualisations from FastAPI, which lists every discussion
 * that already has cached analytics on disk (i.e. has_analytics=true).
 * Returns an array of discussion summaries enriched with cached analytics
 * payloads — useful for the analytics listing/gallery page.
 */
export async function GET(): Promise<NextResponse> {
  log.info("request_started", "GET /api/visualisations");

  if (serverEnv.mockBackend) {
    log.info("request_completed", "GET /api/visualisations (mock)", { source: "mock" });
    return NextResponse.json([]);
  }

  try {
    const upstream = await fetch(`${serverEnv.fastapiUrl}/visualisations`, {
      signal: AbortSignal.timeout(15_000),
    });

    if (!upstream.ok) {
      log.warn("request_failed", "GET /visualisations upstream failed", {
        status: upstream.status,
      });
      return NextResponse.json(
        { error: { code: "upstream_error", message: `Upstream returned ${upstream.status}` } },
        { status: upstream.status },
      );
    }

    const data = await upstream.json();
    log.info("request_completed", "GET /api/visualisations", {
      count: Array.isArray(data) ? data.length : "?",
    });
    return NextResponse.json(data);
  } catch (err) {
    log.error("request_failed", "GET /api/visualisations fetch error", {
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: { code: "engine_error", message: "Network error reaching backend." } },
      { status: 502 },
    );
  }
}
