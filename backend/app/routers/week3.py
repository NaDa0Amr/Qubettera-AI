from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.schemas.week3 import DiscussRequest
from backend.app.services.week3_events import stream_discussion

router = APIRouter(prefix="/week3", tags=["week3"])


@router.post("/discuss")
async def discuss(payload: DiscussRequest) -> StreamingResponse:
    """Start a Week 3 discussion and stream its events as SSE.

    Event types emitted:
        stream_started, discussion_started, turn_completed,
        discussion_completed, discussion_failed,
        and token_chunk (per LLM token, if the token sink is registered
        before the runtime is built — see week3_events.py).

    The full transcript is also written to
    <WEEK3_OUTPUT_DIR>/<discussion_id>.jsonl, which is what /week4/analytics
    later reads.
    """
    if payload.num_rounds < 3:
        raise HTTPException(status_code=422, detail="num_rounds must be at least 3.")

    discussion_id = str(uuid4())
    return StreamingResponse(
        stream_discussion(payload, discussion_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disables response buffering in nginx and similar reverse proxies.
            # Without it, an SSE stream is accumulated by the proxy and only
            # delivered to the client once the upstream connection closes.
            # Matches the headers used by /week4/analytics/{id}/stream.
            "X-Accel-Buffering": "no",
            "X-Discussion-Id": discussion_id,
        },
    )