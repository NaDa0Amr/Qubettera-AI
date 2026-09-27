import { NextResponse } from "next/server";
import { log } from "@/lib/log";
import { getDiscussions } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  try {
    const discussions = await getDiscussions();
    return NextResponse.json({ discussions });
  } catch (error) {
    log.error("request_failed", "GET /api/discussions", {
      error: error instanceof Error ? error.message : String(error),
    });
    return NextResponse.json(
      { error: "Unable to load discussions. Check the backend connection and try again." },
      { status: 502 },
    );
  }
}
