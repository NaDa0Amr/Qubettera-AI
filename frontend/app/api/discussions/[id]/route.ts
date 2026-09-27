import { NextRequest, NextResponse } from "next/server";
import { log } from "@/lib/log";
import { serverEnv } from "@/lib/env";
import type { DiscussionDetail, DiscussionMessage } from "@/types";

export const dynamic = "force-dynamic";

/**
 * Build a DiscussionDetail envelope from the flat DiscussionMessage[] that
 * FastAPI's GET /discussions/{id} returns.
 *
 * The backend surfaces only the `message` objects extracted from turn_completed
 * events — there is no separate metadata endpoint. We reconstruct all
 * DiscussionDetail fields from what the messages themselves contain:
 *
 *   topic           — first initial message's retrieval_query (best proxy)
 *   participant_ids — unique sender_ids in first-appearance order
 *   num_rounds      — max round_number across all messages
 *   created_at      — first message's created_at
 *   graph.edges     — inferred from recipient_ids per message
 */
function buildDetail(id: string, messages: DiscussionMessage[]): DiscussionDetail {
  // Collect unique participant IDs in first-appearance order.
  const seen = new Set<string>();
  const participantIds: string[] = [];
  for (const m of messages) {
    if (!seen.has(m.sender_id)) {
      seen.add(m.sender_id);
      participantIds.push(m.sender_id);
    }
  }

  const numRounds = messages.reduce((max, m) => Math.max(max, m.round_number), 0);
  const createdAt = messages[0]?.created_at ?? new Date().toISOString();

  // Best-effort topic: retrieval_query of the first initial turn, then a
  // trimmed slice of the first message's content, then the discussion ID.
  const firstInitial = messages.find((m) => m.phase === "initial");
  const topic =
    firstInitial?.retrieval_query ??
    ((firstInitial?.content ?? "").slice(0, 120) || id);

  // Build directed graph edges from recipient_ids on each message.
  const edgeSet = new Set<string>();
  const edges: [string, string][] = [];
  for (const m of messages) {
    for (const recipientId of m.recipient_ids ?? []) {
      const key = `${m.sender_id}→${recipientId}`;
      if (!edgeSet.has(key)) {
        edgeSet.add(key);
        edges.push([m.sender_id, recipientId]);
      }
    }
  }

  return {
    discussion_id: id,
    topic,
    created_at: createdAt,
    status: "completed" as DiscussionDetail["status"],
    config: {
      brief: {
        objective: topic,
        constraints: [],
        topics: [topic],
        strict_notes: [],
      },
      participant_ids: participantIds,
      num_rounds: numRounds,
      model_config: {},
    },
    graph: {
      directed: true,
      nodes: participantIds,
      edges,
    },
    messages,
  };
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  log.info("request_started", "GET /api/discussions/[id]", { discussion_id: id });

  if (serverEnv.mockBackend) {
    return NextResponse.json(
      { error: { code: "discussion_not_found", message: "Mock mode: no stored transcripts." } },
      { status: 404 },
    );
  }

  try {
    const upstream = await fetch(`${serverEnv.fastapiUrl}/discussions/${id}`, {
      signal: AbortSignal.timeout(15_000),
    });

    if (!upstream.ok) {
      const code = upstream.status === 404 ? "discussion_not_found" : "engine_error";
      log.warn("request_failed", "GET /discussions/{id} upstream failed", {
        status: upstream.status,
        discussion_id: id,
      });
      return NextResponse.json(
        { error: { code, message: `Upstream returned ${upstream.status}` } },
        { status: upstream.status },
      );
    }

    const raw = await upstream.json();

    // Backend now returns { messages: DiscussionMessage[], status: string }.
    // Guard: if a future version already returns DiscussionDetail, pass through.
    let detail: DiscussionDetail;
    if (Array.isArray(raw)) {
      // Legacy flat array — old backend version.
      detail = buildDetail(id, raw as DiscussionMessage[]);
    } else if (Array.isArray((raw as { messages?: unknown }).messages)) {
      // New shape: { messages, status }
      const typed = raw as { messages: DiscussionMessage[]; status: string };
      detail = buildDetail(id, typed.messages);
      detail.status =
        (typed.status as DiscussionDetail["status"]) ?? "completed";
    } else {
      // Already a DiscussionDetail — ensure messages array exists.
      const d = raw as DiscussionDetail;
      detail = { ...d, messages: d.messages ?? [] };
    }

    log.info("request_completed", "GET /api/discussions/[id]", {
      discussion_id: id,
      message_count: detail.messages.length,
    });
    return NextResponse.json(detail);
  } catch (err) {
    log.error("request_failed", "GET /api/discussions/[id] fetch error", {
      discussion_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return NextResponse.json(
      { error: { code: "engine_error", message: "Network error reaching backend." } },
      { status: 502 },
    );
  }
}
