from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from backend.app.core import config
from backend.app.schemas.identifiers import DiscussionId
from backend.app.schemas.week4 import AnalyticsResponse
from backend.app.services.analytics_runner import (
    AnalyticsEngineError,
    DiscussionNotFound,
    get_analytics as run_analytics,
    stream_analytics,
)

router = APIRouter(prefix="/week4", tags=["week4"])


@router.get("/analytics/{discussion_id}", response_model=AnalyticsResponse)
async def get_analytics(discussion_id: DiscussionId, refresh: bool = False) -> dict:
    """Return the unified Week 4 analytics result for one Week 3 discussion.

    `refresh=true` forces recomputation, which reruns the stance-scoring
    LLM calls — slower and not free, so it's opt-in.
    """
    try:
        return await run_analytics(discussion_id, refresh=refresh)
    except DiscussionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AnalyticsEngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/analytics/{discussion_id}/stream")
async def get_analytics_stream(discussion_id: DiscussionId, refresh: bool = False) -> StreamingResponse:
    """Async/SSE version of /week4/analytics/{id} (B4, Blocker).

    Emits `stream_started`, then `metric_started` / `metric_completed` /
    `metric_failed` for each of opinion_change, agreement, influence,
    sentiment, report, visuals, then `analytics_completed` (or
    `analytics_failed` — see stream_analytics()'s docstring for the timing
    caveat: metric_completed events currently arrive together rather than
    as each metric individually finishes inside the engine subprocess).
    """
    return StreamingResponse(
        stream_analytics(discussion_id, refresh=refresh),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Discussion-Id": discussion_id,
        },
    )


@router.get("/report/{discussion_id}")
async def get_report(discussion_id: DiscussionId) -> Response:
    """Return reports/report_<id>.md as text/markdown (B5)."""
    path = config.ANALYTICS_OUT_DIR / f"report_{discussion_id}.md"
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"No report for id={discussion_id!r} at {path}."
        )
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


# name -> filename template, per new-endpoints.md B6.
_VISUAL_FILENAMES = {
    "opinion_trajectory": "opinion_trajectory_{id}.png",
    "interaction_graph": "interaction_graph_{id}.png",
}


@router.get("/visuals/{discussion_id}/{name}")
async def get_visual(discussion_id: DiscussionId, name: str) -> FileResponse:
    """Serve one of the two generated PNGs for a discussion (B6).

    `name` must be `opinion_trajectory` or `interaction_graph`.
    """
    template = _VISUAL_FILENAMES.get(name)
    if template is None:
        raise HTTPException(
            status_code=422,
            detail=f"name must be one of {sorted(_VISUAL_FILENAMES)}, got {name!r}.",
        )

    path = config.ANALYTICS_VISUALS_DIR / template.format(id=discussion_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Visual not generated yet: {path}.")

    return FileResponse(path, media_type="image/png")
