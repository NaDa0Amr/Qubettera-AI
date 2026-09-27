// SSE chunk parser.
// Handles chunk boundaries, multiple events per chunk, and partial trailing
// events that arrive across chunk boundaries.

export interface SSEEvent {
  event: string;
  data: unknown;
}

/**
 * Parse one or more SSE events from a raw chunk string.
 *
 * @param chunk - The newly received text chunk from the stream reader.
 * @param buffer - Any incomplete block carried over from the previous chunk.
 * @returns Fully parsed events and the new buffer remainder.
 */
export function parseSSEChunk(
  chunk: string,
  buffer: string,
): { events: SSEEvent[]; remaining: string } {
  // Blocks are separated by double newlines.
  const combined = buffer + chunk;
  const blocks = combined.split("\n\n");

  // The last element may be incomplete — carry it forward as the new buffer.
  const remaining = blocks.pop() ?? "";

  const events: SSEEvent[] = [];

  for (const block of blocks) {
    if (!block.trim()) continue;

    let eventType = "message";
    const dataLines: string[] = [];

    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        dataLines.push(line.slice(6));
      }
      // Comment lines (starting with ":") are intentionally ignored.
    }

    if (dataLines.length === 0) continue;

    try {
      events.push({
        event: eventType,
        data: JSON.parse(dataLines.join("\n")) as unknown,
      });
    } catch {
      // Malformed JSON — skip the event and continue. The caller logs this.
      console.warn("[sse] Skipping malformed SSE block", { eventType });
    }
  }

  return { events, remaining };
}
