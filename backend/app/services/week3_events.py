"""Stream shared orchestrator events and persist the same transcript."""
import asyncio
from contextlib import ExitStack
import json
import logging
import queue
import threading
from uuid import uuid4
from backend.app.core import config
from backend.app.schemas.week3 import DiscussRequest
from backend.app.services.topic_brief import build_brief_from_topic

logger = logging.getLogger(__name__)
_SENTINEL = object()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _run_discussion_in_thread(*, payload, discussion_id, event_queue):
    file_sink = None
    try:
        from qubettera.discussion.run_log import JsonlEventSink
        from qubettera.agents.graph_builder import GraphBuilder
        from qubettera.discussion.models import DiscussionConfig
        from qubettera.discussion.orchestrator import DiscussionOrchestrator

        file_sink = JsonlEventSink(config.WEEK3_OUTPUT_DIR / f"{discussion_id}.jsonl")

        class Sink:
            def write_event(self, event):
                file_sink.write_event(event)
                event_queue.put(event)

        personas = json.loads(config.DEFAULT_PERSONAS_PATH.read_text(encoding="utf-8"))
        known = {p["id"] for p in personas}
        ids = payload.participant_ids or [p["id"] for p in personas]
        if len(ids) < 2 or len(set(ids)) != len(ids) or set(ids) - known:
            raise ValueError("Choose at least two distinct, known personas.")
        with ExitStack() as stack:
            if payload.mode == "live":
                from qubettera.discussion.week2_adapter import Week2AgentRuntime
                from qubettera.discussion.retrieval_provider import TeamRetrievalProvider
                # queue.Queue is thread-safe. Each agent turn installs its own
                # callback, so parallel model streams retain the right labels.
                runtime = stack.enter_context(Week2AgentRuntime(token_sink=event_queue.put))
                retrieval = TeamRetrievalProvider()
            else:
                from qubettera.discussion.fakes import DeterministicAgentRuntime, DeterministicRetrievalProvider
                runtime = DeterministicAgentRuntime()
                retrieval = DeterministicRetrievalProvider()
            orchestrator = DiscussionOrchestrator(
                graph=GraphBuilder.from_persona_ids(ids), agent_runtime=runtime,
                retrieval_provider=retrieval, event_sink=Sink(),
                id_factory=lambda: discussion_id,
            )
            orchestrator.run(DiscussionConfig(
                brief=build_brief_from_topic(payload.topic),
                participant_ids=tuple(ids), num_rounds=payload.num_rounds,
            ))
    except Exception as exc:
        logger.exception("Discussion %s failed", discussion_id)
        event = {"event": "discussion_failed", "discussion_id": discussion_id, "error": str(exc)}
        try:
            if file_sink is not None:
                file_sink.write_event(event)
        finally:
            event_queue.put(event)
    finally:
        event_queue.put(_SENTINEL)


async def stream_discussion(payload: DiscussRequest, discussion_id: str | None = None):
    discussion_id = discussion_id or str(uuid4())
    events = queue.Queue()
    threading.Thread(target=_run_discussion_in_thread, kwargs=dict(
        payload=payload, discussion_id=discussion_id, event_queue=events,
    ), daemon=True).start()
    yield _sse("stream_started", {"discussion_id": discussion_id})
    while True:
        try:
            item = await asyncio.to_thread(events.get, True, 15)
        except queue.Empty:
            yield ": ping\n\n"
            continue
        if item is _SENTINEL:
            return
        yield _sse(item.get("event", "message"), item)
