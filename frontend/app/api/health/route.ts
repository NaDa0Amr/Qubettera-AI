import { NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { HealthResponse } from "@/types";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse<HealthResponse>> {
  log.info("request_started", "GET /api/health");

  let backendOk = false;
  let backendReady = false;

  try {
    const [livenessRes, readinessRes] = await Promise.allSettled([
      fetch(`${serverEnv.fastapiUrl}/health`, { signal: AbortSignal.timeout(5000) }),
      fetch(`${serverEnv.fastapiUrl}/health/ready`, { signal: AbortSignal.timeout(5000) }),
    ]);

    if (livenessRes.status === "fulfilled" && livenessRes.value.ok) {
      backendOk = true;
    }

    if (readinessRes.status === "fulfilled") {
      // Backend returns 200 when ready, 503 when degraded — both are reachable.
      const body = await readinessRes.value.json() as { status?: string };
      backendReady = body.status === "ready";
    }
  } catch (err) {
    log.warn("request_failed", "Backend health check unreachable", {
      error: err instanceof Error ? err.message : String(err),
    });
  }

  const payload: HealthResponse = {
    nextjs: "ok",
    backend: backendOk ? "ok" : "down",
    backend_ready: backendReady,
    checked_at: new Date().toISOString(),
  };

  log.info("request_completed", "GET /api/health", {
    backend: payload.backend,
    backend_ready: payload.backend_ready,
  });

  // Always return HTTP 200. The JSON body carries the truth.
  // This prevents container health-check flapping when the backend is temporarily unavailable.
  return NextResponse.json(payload, { status: 200 });
}
