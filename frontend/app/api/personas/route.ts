import { NextResponse } from "next/server";
import { log } from "@/lib/log";
import { getPersonas } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  try {
    const personas = await getPersonas();
    return NextResponse.json({ personas });
  } catch (error) {
    log.error("request_failed", "GET /api/personas", {
      error: error instanceof Error ? error.message : String(error),
    });
    return NextResponse.json(
      { error: "Unable to load personas. Check the backend connection and try again." },
      { status: 502 },
    );
  }
}
