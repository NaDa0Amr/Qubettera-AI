"""Run the shared analytics engine without legacy repositories or subprocesses."""
import asyncio
import json
import logging
from backend.app.core import config
from backend.app.services.week3_events import _sse

logger = logging.getLogger(__name__)
_METRIC_KEYS = ("opinion_change", "agreement", "influence", "sentiment", "report", "visuals")
_tasks: dict[str, asyncio.Task] = {}


class DiscussionNotFound(Exception):
    pass


class AnalyticsEngineError(Exception):
    pass


def discussion_log_path(discussion_id):
    return config.WEEK3_OUTPUT_DIR / f"{discussion_id}.jsonl"


def cached_result_path(discussion_id):
    return config.ANALYTICS_OUT_DIR / f"analytics_{discussion_id}.json"


def report_path(discussion_id):
    return config.ANALYTICS_OUT_DIR / f"report_{discussion_id}.md"


def visual_paths(discussion_id):
    return {name: config.ANALYTICS_VISUALS_DIR / f"{name}_{discussion_id}.png"
            for name in ("opinion_trajectory", "interaction_graph")}


def _compute(discussion_id):
    from qubettera.analytics.engine import get_analytics, save_analytics
    from qubettera.analytics.report import write_report
    from qubettera.analytics.visualize import create_visualizations
    path = discussion_log_path(discussion_id)
    if not path.is_file():
        raise DiscussionNotFound(f"No discussion log for {discussion_id}.")
    try:
        result = get_analytics(path)
        config.ANALYTICS_OUT_DIR.mkdir(parents=True, exist_ok=True)
        create_visualizations(result, config.ANALYTICS_VISUALS_DIR)
        write_report(result, report_path(discussion_id), visuals_dir=config.ANALYTICS_VISUALS_DIR)
        save_analytics(result, config.ANALYTICS_OUT_DIR)
        return result
    except Exception as exc:
        logger.exception("Analytics failed for %s", discussion_id)
        raise AnalyticsEngineError(str(exc)) from exc


async def get_analytics(discussion_id, *, refresh=False):
    # Share a running task across JSON and SSE requests. Shielding lets the
    # computation finish and persist its result if a browser disconnects.
    task = _tasks.get(discussion_id)
    if task is not None and not task.done():
        return await asyncio.shield(task)
    path = cached_result_path(discussion_id)
    if path.is_file() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    task = asyncio.create_task(asyncio.to_thread(_compute, discussion_id))
    _tasks[discussion_id] = task
    def finished(done):
        if _tasks.get(discussion_id) is done:
            _tasks.pop(discussion_id, None)
        if not done.cancelled():
            done.exception()
    task.add_done_callback(finished)
    return await asyncio.shield(task)


async def stream_analytics(discussion_id, *, refresh=False):
    yield _sse("stream_started", {"discussion_id": discussion_id})
    for metric in _METRIC_KEYS:
        yield _sse("metric_started", {"discussion_id": discussion_id, "metric": metric})
    task = asyncio.create_task(get_analytics(discussion_id, refresh=refresh))
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=15)
            if not done:
                yield ": ping\n\n"
        result = task.result()
        for metric in _METRIC_KEYS:
            data = result.get(metric)
            if metric == "report" and report_path(discussion_id).is_file():
                data = {"path": f"/week4/report/{discussion_id}"}
            if metric == "visuals":
                urls = {name: f"/week4/visuals/{discussion_id}/{name}"
                        for name, path in visual_paths(discussion_id).items() if path.is_file()}
                data = {"urls": urls} if urls else None
            if data is None:
                yield _sse("metric_failed", {"discussion_id": discussion_id, "metric": metric,
                                             "error": "Artifact is unavailable"})
            else:
                yield _sse("metric_completed", {"discussion_id": discussion_id, "metric": metric, "data": data})
        yield _sse("analytics_completed", {"discussion_id": discussion_id, "result": result})
    except Exception as exc:
        yield _sse("analytics_failed", {"discussion_id": discussion_id, "error": str(exc)})
    finally:
        if not task.done():
            task.cancel()
