"""Measure each participant opinion against one fixed proposition."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .loader import DiscussionLog, discover_discussion_files, load_discussion
from .stance_scorer import StanceScorer


def _round_stances(
    log: DiscussionLog, scorer: StanceScorer, proposition: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for agent_id in log.agent_ids:
        previous_stance: float | None = None
        for snapshot in log.snapshots_for(agent_id):
            result = scorer.score(
                proposition=proposition,
                opinion_text=snapshot.opinion_text,
                round_number=snapshot.round_number,
            )
            change = None if previous_stance is None else round(result.stance - previous_stance, 4)
            rows.append(
                {
                    "agent_id": agent_id,
                    "round": snapshot.round_number,
                    "stance": round(result.stance, 4),
                    "change": change,
                    "reasoning": result.reasoning,
                }
            )
            previous_stance = result.stance

    return rows


def track_opinion_change(
    discussion_path: str | Path | DiscussionLog,
    scorer: StanceScorer | None = None,
) -> dict[str, Any]:
    """Load a Week 3 discussion log and produce the opinion-change table.

    Returns a dict with the proposition used (for documentation/report
    purposes) and the row-per-agent-per-round table.
    """
    log = (
        discussion_path if isinstance(discussion_path, DiscussionLog)
        else load_discussion(discussion_path)
    )
    proposition = log.proposition()
    scorer = scorer or StanceScorer()
    rows = _round_stances(log, scorer, proposition)
    return {
        "discussion_id": log.discussion_id,
        "proposition": proposition,
        "rows": rows,
    }


def track_opinion_change_batch(
    directory: str | Path,
    scorer: StanceScorer | None = None,
    on_error: str = "skip",
) -> dict[str, dict[str, Any]]:
    """Run track_opinion_change over every discussion file in `directory`.

    """
    scorer = scorer or StanceScorer()
    results: dict[str, dict[str, Any]] = {}

    for file_path in discover_discussion_files(directory):
        try:
            result = track_opinion_change(file_path, scorer=scorer)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see on_error
            if on_error == "raise":
                raise
            print(f"[opinion_change] skipping {file_path.name}: {exc}")
            continue
        results[result["discussion_id"]] = result

    return results


def rows_by_agent(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Convenience reshape: {agent_id: [rows sorted by round]}."""
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(rows, key=lambda r: (r["agent_id"], r["round"])):
        by_agent.setdefault(row["agent_id"], []).append(row)
    return by_agent

