import { NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { Persona } from "@/types";
import mockPersonas from "@/lib/mocks/personas.json";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  log.info("request_started", "GET /api/personas");

  // Serve mock data when MOCK_BACKEND is enabled.
  if (serverEnv.mockBackend) {
    log.info("request_completed", "GET /api/personas (mock)", { source: "mock" });
    return NextResponse.json(mockPersonas);
  }

  try {
    const upstream = await fetch(`${serverEnv.fastapiUrl}/personas`, {
      signal: AbortSignal.timeout(10_000),
    });

    if (!upstream.ok) {
      // New endpoint may not exist yet — fall back to mock rather than erroring.
      log.warn("request_failed", "GET /personas upstream failed, falling back to mock", {
        status: upstream.status,
      });
      return NextResponse.json(mockPersonas);
    }

    const raw = await upstream.json();
    // FastAPI returns a flat Persona[] array. Normalize into the wrapped
    // { personas: [] } shape the frontend types / hooks expect uniformly.
    const personas: Persona[] = Array.isArray(raw)
      ? (raw as Persona[])
      : ((raw as { personas: Persona[] }).personas ?? []);
    log.info("request_completed", "GET /api/personas", { count: personas.length });
    return NextResponse.json({ personas });
  } catch (err) {
    log.error("request_failed", "GET /api/personas fetch error, falling back to mock", {
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(mockPersonas);
  }
}
