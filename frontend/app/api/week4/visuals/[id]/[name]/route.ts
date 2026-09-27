import { NextRequest, NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

const VALID_VISUALS = new Set(["opinion_trajectory", "interaction_graph"]);

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; name: string }> },
): Promise<NextResponse | Response> {
  const { id, name } = await params;
  log.info("request_started", "GET /api/week4/visuals/[id]/[name]", {
    discussion_id: id,
    visual: name,
  });

  if (!VALID_VISUALS.has(name)) {
    return NextResponse.json(
      { error: { code: "visual_not_ready", message: `Unknown visual: ${name}` } },
      { status: 400 },
    );
  }

  if (serverEnv.mockBackend) {
    return NextResponse.json(
      { error: { code: "visual_not_ready", message: "Visuals not available in mock mode." } },
      { status: 404 },
    );
  }

  try {
    const upstream = await fetch(
      `${serverEnv.fastapiUrl}/week4/visuals/${id}/${name}`,
      { signal: AbortSignal.timeout(30_000) },
    );

    if (!upstream.ok) {
      const code = upstream.status === 404 ? "visual_not_ready" : "engine_error";
      log.warn("request_failed", "GET /week4/visuals upstream failed", {
        status: upstream.status,
        discussion_id: id,
        visual: name,
      });
      return NextResponse.json(
        { error: { code, message: `Visual not available (${upstream.status})` } },
        { status: upstream.status },
      );
    }

    const buffer = await upstream.arrayBuffer();
    log.info("request_completed", "GET /api/week4/visuals/[id]/[name]", {
      discussion_id: id,
      visual: name,
      bytes: buffer.byteLength,
    });

    return new Response(buffer, {
      headers: { "Content-Type": "image/png" },
    });
  } catch (err) {
    log.error("request_failed", "GET /api/week4/visuals/[id]/[name] error", {
      discussion_id: id,
      visual: name,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: { code: "engine_error", message: "Network error reaching backend." } },
      { status: 502 },
    );
  }
}
