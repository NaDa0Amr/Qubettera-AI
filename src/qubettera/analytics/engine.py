"""Combine opinion change, agreement, influence, and sentiment into one result."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agreement import measure_agreement
from .influence import estimate_influence
from .loader import DiscussionLog, load_discussion
from .opinion_change import track_opinion_change
from .sentiment import (
    SentimentScorer,
    aggregate_by_agent,
    aggregate_by_round,
    score_sentiment,
    sentiment_distribution,
)
from .stance_scorer import StanceScorer


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with seconds precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract_task1_fields(
    task1_result: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Pull ``rows`` and ``proposition`` out of a pre-computed Task 1 result.

    Returns ``(None, None)`` when ``task1_result`` is None so the caller
    can fall through to computing Task 1 itself.

    Raises ``ValueError`` if ``task1_result`` is provided but does not
    contain the expected ``"rows"`` key â€” this catches stale or malformed
    cache files before they silently corrupt the analytics output.
    """
    if task1_result is None:
        return None, None
    if "rows" not in task1_result:
        raise ValueError(
            "task1_result was provided but is missing the 'rows' key; "
            "expected the dict returned by opinion_change.track_opinion_change()"
        )
    return task1_result["rows"], task1_result.get("proposition")


def _validate_precomputed_stances(log: DiscussionLog, result: dict[str, Any]) -> None:
    """Reject cached rows that do not describe this exact discussion."""
    if result.get("discussion_id") != log.discussion_id or result.get("proposition") != log.proposition():
        raise ValueError("Precomputed stance result has a different discussion or proposition")
    rows = result.get("rows")
    if not isinstance(rows, list):
        raise ValueError("Precomputed stance rows must be a list")
    expected = {(s.agent_id, s.round_number) for s in log.snapshots}
    actual: set[tuple[str, int]] = set()
    for row in rows:
        try:
            key = (row["agent_id"], row["round"])
            stance = float(row["stance"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Precomputed stance row is malformed") from exc
        if not isinstance(key[0], str) or type(key[1]) is not int:
            raise ValueError("Precomputed stance row has invalid agent or round")
        if key in actual or not math.isfinite(stance) or not -1 <= stance <= 1:
            raise ValueError("Precomputed stance rows contain duplicates or invalid scores")
        actual.add(key)
    if actual != expected:
        raise ValueError("Precomputed stance rows do not cover every participant round")


# ---------------------------------------------------------------------------
# Public API â€” unified entry point
# ---------------------------------------------------------------------------

def get_analytics(
    discussion_path: str | Path,
    *,
    stance_scorer: StanceScorer | None = None,
    sentiment_scorer: SentimentScorer | None = None,
    task1_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full analytics pipeline on one Week 3 discussion file.

    Parameters
    ----------
    discussion_path : str | Path
        Path to a saved ``outputs/discussions/<discussion_id>.jsonl`` file.
    stance_scorer : StanceScorer, optional
        Used for Task 1 when ``task1_result`` is not provided. If omitted,
        a default scorer is constructed, which requires a configured LLM
        provider (see ``stance_scorer.StanceScorer``).
    sentiment_scorer : SentimentScorer, optional
        Used for Task 4. If omitted, a default Tier 1 scorer is constructed,
        which loads a transformer model on first use. Tests should always
        supply a scorer with an injected fake pipeline.
    task1_result : dict, optional
        Pre-computed Task 1 output (the dict returned by
        ``opinion_change.track_opinion_change``). When provided, Task 1 is
        not re-run, so no LLM call is made. Useful when the result was
        already cached by a previous run.

    Returns
    -------
    dict
        The unified analytics result described in the module docstring.

    Raises
    ------
    FileNotFoundError
        If ``discussion_path`` does not exist.
    ValueError
        If the discussion file is malformed, contains only stub text, or
        ``task1_result`` is provided but missing the ``"rows"`` key.
    """
    # --- Load discussion --------------------------------------------------
    log: DiscussionLog = load_discussion(discussion_path)
    if task1_result is not None:
        _validate_precomputed_stances(log, task1_result)

    # --- Task 1: Opinion Change -------------------------------------------
    rows, cached_proposition = _extract_task1_fields(task1_result)
    if rows is not None:
        # Pre-computed: no LLM call.
        proposition = cached_proposition or log.proposition()
        task1_from_cache = True
        stance_model_name: str | None = None
        stance_num_samples: int | None = None
    else:
        # Run Task 1 for real (requires LLM).
        if stance_scorer is None:
            stance_scorer = StanceScorer()
        t1 = track_opinion_change(log, scorer=stance_scorer)
        rows = t1["rows"]
        proposition = t1["proposition"]
        task1_from_cache = False
        stance_model_name = getattr(stance_scorer, "model", None)
        stance_num_samples = getattr(stance_scorer, "num_samples", None)

    # --- Task 2: Agreement ------------------------------------------------
    agreement = measure_agreement(rows)

    # --- Task 3: Influence ------------------------------------------------
    # DiscussionLog.edges is a tuple of tuples because DiscussionLog is a
    # frozen dataclass. The influence module declares list[tuple] | list[list];
    # convert the outer container here. No change is required in influence.py.
    influence, influence_edges = estimate_influence(rows, log.edges, log.snapshots)

    # --- Task 4: Sentiment ------------------------------------------------
    if sentiment_scorer is None:
        sentiment_scorer = SentimentScorer()
    sentiment_messages = score_sentiment(log, scorer=sentiment_scorer)
    if len(sentiment_messages) != len(log.snapshots):
        raise ValueError("Sentiment scorer did not return one result per participant message")
    sentiment_payload = {
        "messages": sentiment_messages,
        "by_agent": aggregate_by_agent(sentiment_messages),
        "by_round": aggregate_by_round(sentiment_messages),
        "distribution": sentiment_distribution(sentiment_messages),
        "method": sentiment_scorer.model_name,
    }

    # --- Assemble ---------------------------------------------------------
    return {
        "discussion_id": log.discussion_id,
        "proposition": proposition,
        "objective": log.objective,
        "topics": list(log.topics),
        "agent_ids": list(log.agent_ids),
        "edges": [list(e) for e in log.edges],
        "rounds": log.rounds(),
        "opinion_change": rows,
        "agreement": agreement,
        "influence": influence,
        "influence_edges": influence_edges,
        "sentiment": sentiment_payload,
        "metadata": {
            "generated_at": _utc_now_iso(),
            "stance_model": stance_model_name,
            "sentiment_model": sentiment_scorer.model_name,
            "stance_num_samples": stance_num_samples,
            "task1_from_cache": task1_from_cache,
        },
    }


# ---------------------------------------------------------------------------
# Public API â€” persistence helper
# ---------------------------------------------------------------------------

def save_analytics(result: dict[str, Any], out_dir: str | Path) -> Path:
    """Write a unified analytics result to ``<out_dir>/analytics_<id>.json``.

    Parameters
    ----------
    result : dict
        The dict returned by ``get_analytics``.
    out_dir : str | Path
        Directory to write into. Created if it does not exist.

    Returns
    -------
    Path
        The path that was written.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"analytics_{result['discussion_id']}.json"
    # default=str handles any unexpected non-serializable value (e.g. a
    # numpy float that slipped through a task boundary) without crashing.
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Public API â€” cache lookup
# ---------------------------------------------------------------------------

def load_cached_task1(
    discussion_id: str,
    cache_dir: str | Path,
) -> dict[str, Any] | None:
    """Load a previously saved opinion-change result.

    Returns ``None`` if no cache file exists for this discussion. Used by
    ``scripts/run_engine.py`` so re-running the pipeline does not repeat the
    LLM stance scoring when a cached result is already available.

    Parameters
    ----------
    discussion_id : str
        Discussion identifier, e.g. ``"425315e8-326c-45b2-..."``.
    cache_dir : str | Path
        Directory to look in, typically ``reports/``.
    """
    path = Path(cache_dir) / f"opinion_change_{discussion_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A malformed or unreadable cache file should not crash the run;
        # the caller will fall through to computing Task 1 fresh.
        return None

