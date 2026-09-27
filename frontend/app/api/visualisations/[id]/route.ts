import { NextRequest, NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * GET /api/visualisations/[id]
 *
 * Proxies GET /visualisations/{id} from FastAPI — returns the full cached
 * analytics payload for a single discussion (equivalent to
 * GET /week4/analytics/{id} but reads only from disk cache, never recomputes).
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  log.info("request_started", "GET /api/visualisations/[id]", { discussion_id: id });

  if (serverEnv.mockBackend) {
    return NextResponse.json(
      { error: { code: "not_found", message: "No cached analytics in mock mode." } },
      { status: 404 },
    );
  }

  try {
    const upstream = await fetch(`${serverEnv.fastapiUrl}/visualisations/${id}`, {
      signal: AbortSignal.timeout(15_000),
    });

    if (!upstream.ok) {
      const code = upstream.status === 404 ? "discussion_not_found" : "engine_error";
      log.warn("request_failed", "GET /visualisations/{id} upstream failed", {
        status: upstream.status,
        discussion_id: id,
      });
      return NextResponse.json(
        { error: { code, message: `Upstream returned ${upstream.status}` } },
        { status: upstream.status },
      );
    }

    const data = await upstream.json();
    log.info("request_completed", "GET /api/visualisations/[id]", { discussion_id: id });
    return NextResponse.json(data);
  } catch (err) {
    log.error("request_failed", "GET /api/visualisations/[id] fetch error", {
      discussion_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: { code: "engine_error", message: "Network error reaching backend." } },
      { status: 502 },
    );
  }
}
