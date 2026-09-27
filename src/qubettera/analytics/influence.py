"""Estimate association between routed messages and later stance movement."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Iterable

from .loader import OpinionSnapshot


_STOPWORDS = {"a", "an", "and", "are", "for", "from", "in", "is", "of", "on", "or", "the", "to", "with"}


def _terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]+", text.lower()) if len(term) > 2 and term not in _STOPWORDS}


def _overlap(left: str, right: str) -> float:
    a, b = _terms(left), _terms(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    x_mean, y_mean = sum(x) / len(x), sum(y) / len(y)
    dx, dy = [v - x_mean for v in x], [v - y_mean for v in y]
    denominator = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return sum(a * b for a, b in zip(dx, dy)) / denominator if denominator > 1e-12 else None


def estimate_influence(
    rows: list[dict[str, Any]],
    edges: Iterable[tuple[str, str] | list[str]],
    snapshots: Iterable[OpinionSnapshot],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return per-agent and per-edge association estimates.

    Edge correlation compares the sender-minus-recipient stance gap in round t
    with the recipient stance change in round t+1. Mean token overlap between
    the sender's routed message and the recipient's next message scales that
    correlation. At least three usable transitions and nonzero variance are
    required. Scores describe association, not causation.
    """
    stances: dict[tuple[str, int], float] = {}
    agents: list[str] = []
    for row in rows:
        agent, round_number, stance = str(row["agent_id"]), int(row["round"]), float(row["stance"])
        if not math.isfinite(stance) or not -1 <= stance <= 1:
            raise ValueError(f"Invalid stance for {agent} in round {round_number}")
        key = (agent, round_number)
        if key in stances:
            raise ValueError(f"Duplicate stance for {agent} in round {round_number}")
        stances[key] = stance
        if agent not in agents:
            agents.append(agent)
    messages = {(s.agent_id, s.round_number): s for s in snapshots}
    rounds = sorted({round_number for _, round_number in stances})
    edge_rows: list[dict[str, Any]] = []
    for source, target in edges:
        gaps: list[float] = []
        changes: list[float] = []
        overlaps: list[float] = []
        for current, following in zip(rounds, rounds[1:]):
            if following != current + 1:
                continue
            sender = messages.get((source, current))
            recipient_next = messages.get((target, following))
            required = ((source, current), (target, current), (target, following))
            if (sender is None or recipient_next is None or target not in sender.recipient_ids
                or not sender.content_text.strip() or not recipient_next.content_text.strip()
                or any(key not in stances for key in required)):
                continue
            gaps.append(stances[(source, current)] - stances[(target, current)])
            changes.append(stances[(target, following)] - stances[(target, current)])
            overlaps.append(_overlap(sender.content_text, recipient_next.content_text))
        correlation = _pearson(gaps, changes)
        note = None
        if len(gaps) < 3:
            note = "insufficient_transitions"
        elif correlation is None:
            note = "no_stance_variation"
        lexical_overlap = sum(overlaps) / len(overlaps) if overlaps else None
        score = round(correlation * lexical_overlap, 4) if correlation is not None else None
        edge_rows.append({
            "source": source, "target": target, "influence": score,
            "correlation": round(correlation, 4) if correlation is not None else None,
            "lexical_overlap": round(lexical_overlap, 4) if lexical_overlap is not None else None,
            "n_transitions": len(gaps), "note": note,
        })
    by_source: dict[str, list[float]] = defaultdict(list)
    for row in edge_rows:
        if row["influence"] is not None:
            by_source[row["source"]].append(row["influence"])
    agent_rows = [{
        "agent_id": agent,
        "influence": round(sum(by_source[agent]) / len(by_source[agent]), 4) if by_source[agent] else None,
        "condition_number": None,
        "note": None if by_source[agent] else "insufficient_edge_data",
    } for agent in agents]
    return agent_rows, edge_rows


def calculate_influence(
    rows: list[dict[str, Any]],
    edges: Iterable[tuple[str, str] | list[str]],
    snapshots: Iterable[OpinionSnapshot] = (),
) -> list[dict[str, Any]]:
    """Compatibility entry point returning per-agent influence rows."""
    return estimate_influence(rows, edges, snapshots)[0]
