import { NextRequest, NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse | Response> {
  const { id } = await params;
  log.info("request_started", "GET /api/week4/report/[id]", { discussion_id: id });

  if (serverEnv.mockBackend) {
    const mockReport = `# Analytics Report — Mock Discussion\n\n**Discussion ID**: ${id}\n\nThis is a placeholder report generated in mock mode. Connect a real backend to generate a full analytics report.\n\n## Summary\n\nThe four-agent debate on MoE vs Dense architectures reached moderate consensus (74% agreement) over three rounds. Hybrid architectures emerged as the convergence point.\n`;
    return new Response(mockReport, {
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
    });
  }

  try {
    const upstream = await fetch(`${serverEnv.fastapiUrl}/week4/report/${id}`, {
      signal: AbortSignal.timeout(30_000),
    });

    if (!upstream.ok) {
      const code = upstream.status === 404 ? "report_not_ready" : "engine_error";
      log.warn("request_failed", "GET /week4/report/{id} upstream failed", {
        status: upstream.status,
        discussion_id: id,
      });
      return NextResponse.json(
        { error: { code, message: `Report not available (${upstream.status})` } },
        { status: upstream.status },
      );
    }

    const text = await upstream.text();
    log.info("request_completed", "GET /api/week4/report/[id]", {
      discussion_id: id,
      bytes: text.length,
    });

    return new Response(text, {
      headers: { "Content-Type": "text/markdown; charset=utf-8" },
    });
  } catch (err) {
    log.error("request_failed", "GET /api/week4/report/[id] error", {
      discussion_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: { code: "engine_error", message: "Network error reaching backend." } },
      { status: 502 },
    );
  }
}
