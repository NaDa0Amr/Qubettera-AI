from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.core import config
from backend.app.schemas.identifiers import DiscussionId
from backend.app.services import analytics_runner

logger = logging.getLogger("app.routers.discussions")
router = APIRouter(tags=["discussions"])


def _iter_events(path: Path):
    """Yield parsed JSON events from a .jsonl file, skipping bad lines.

    A discussion that failed mid-write (process killed, disk full, ...)
    can leave a truncated last line. One bad line shouldn't hide every
    other event in the file, so this logs and skips rather than raising.
    """
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping malformed JSON at %s:%d", path, lineno)
                continue


def _summarize_discussion(path: Path) -> dict[str, Any] | None:
    """Build one /discussions row from a <discussion_id>.jsonl file.

    NOTE — assumption flagged for review: the exact field names on the
    `discussion_started` event (e.g. whether it's `topic` vs
    `config.brief.topics[0]`, `participant_ids` vs `config.participant_ids`,
    whether a timestamp is included) are defined by
    week3/orchestrator.py + week3/run_log.JsonlEventSink in the
    Multi-Agent-Collaboration repo, which isn't in this codebase. This reads
    generously across the field names most likely to be used and falls back
    to deriving the same info from `turn_completed` events / file metadata
    when a field is missing, so the endpoint degrades gracefully rather than
    crashing — but the field names below should be checked against a real
    discussion_started payload once you can see one. This is also exactly
    what C8 (are config.brief fields ever omitted?) would settle for real.
    """
    discussion_id = path.stem
    topic: str | None = None
    created_at: str | None = None
    num_rounds: int | None = None
    participant_ids: list[str] | None = None
    status = "unknown"
    turn_count = 0
    sender_ids: set[str] = set()

    for event in _iter_events(path):
        ev_type = event.get("event")

        if ev_type == "discussion_started":
            cfg = event.get("config") or {}
            brief = cfg.get("brief") or {}
            topic = event.get("topic") or (brief.get("topics") or [None])[0]
            created_at = event.get("timestamp") or event.get("created_at")
            ids = event.get("participant_ids") or cfg.get("participant_ids")
            if ids:
                participant_ids = list(ids)
            num_rounds = event.get("num_rounds") or cfg.get("num_rounds")

        elif ev_type == "turn_completed":
            turn_count += 1
            message = event.get("message") or {}
            sender_id = message.get("sender_id")
            if sender_id:
                sender_ids.add(sender_id)

        elif ev_type == "discussion_completed":
            status = "completed"

        elif ev_type == "discussion_failed":
            status = "failed"

    if status == "unknown":
        # No discussion_completed or discussion_failed event was written yet.
        # This means the discussion is either still running or it crashed without
        # emitting a terminal event. Either way the transcript is incomplete, so
        # report "running" so the frontend knows to poll for updates rather than
        # treating the transcript as final.
        status = "running" if turn_count else "empty"

    if created_at is None:
        created_at = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    num_agents = len(participant_ids) if participant_ids else (len(sender_ids) or None)

    has_analytics = analytics_runner.cached_result_path(discussion_id).is_file()

    # Include the status in the DiscussionDetail envelope so the frontend
    # can decide whether to poll for live updates.
    return {
        "discussion_id": discussion_id,
        "topic": topic,
        "created_at": created_at,
        "num_rounds": num_rounds,
        "num_agents": num_agents,
        "status": status,
        "has_analytics": has_analytics,
    }


@router.get("/discussions")
async def list_discussions() -> list[dict]:
    """Summaries of every past discussion run (B2).

    Enumerates <WEEK3_OUTPUT_DIR>/*.jsonl, newest first.
    """
    out_dir = config.WEEK3_OUTPUT_DIR
    if not out_dir.is_dir():
        return []

    summaries = []
    for path in sorted(out_dir.glob("*.jsonl")):
        try:
            summary = _summarize_discussion(path)
        except OSError as exc:
            logger.warning("could not read %s: %s", path, exc)
            continue
        if summary is not None:
            summaries.append(summary)

    summaries.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return summaries


@router.get("/discussions/{discussion_id}")
async def get_discussion(discussion_id: DiscussionId) -> dict:
    """Full transcript of one discussion (B3).

    Returns a DiscussionDetail envelope including:
      - messages: array of `message` objects from each `turn_completed` event
      - status: "running" | "completed" | "failed" | "empty"

    The `status` field is set to "running" for discussions that have at least
    one turn but no terminal event yet, allowing the frontend to poll for
    live updates instead of treating the transcript as final.
    """
    path = config.WEEK3_OUTPUT_DIR / f"{discussion_id}.jsonl"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"No discussion log for id={discussion_id!r} at {path}.",
        )

    # Collect messages AND determine status in one pass through the file.
    messages = []
    status = "unknown"
    for event in _iter_events(path):
        ev_type = event.get("event")
        if ev_type == "turn_completed" and "message" in event:
            messages.append(event["message"])
        elif ev_type == "discussion_completed":
            status = "completed"
        elif ev_type == "discussion_failed":
            status = "failed"

    if status == "unknown":
        status = "running" if messages else "empty"

    return {"messages": messages, "status": status}
