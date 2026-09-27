"""Per-round agreement from pairwise stance distances."""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any


def measure_agreement(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return 1 minus the mean absolute pairwise distance divided by 2."""
    by_round: dict[int, dict[str, float]] = {}
    for index, row in enumerate(rows):
        try:
            agent = str(row["agent_id"])
            round_number = int(row["round"])
            stance = float(row["stance"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid stance row {index}: {row!r}") from exc
        if not agent or round_number < 0 or not math.isfinite(stance) or not -1 <= stance <= 1:
            raise ValueError(f"Invalid stance row {index}: {row!r}")
        bucket = by_round.setdefault(round_number, {})
        if agent in bucket:
            raise ValueError(f"Duplicate stance for {agent} in round {round_number}")
        bucket[agent] = stance

    results: list[dict[str, Any]] = []
    for round_number, stances in sorted(by_round.items()):
        pairs = list(combinations(stances.values(), 2))
        agreement = (
            round(1 - sum(abs(a - b) / 2 for a, b in pairs) / len(pairs), 4)
            if pairs else None
        )
        results.append({
            "round": round_number,
            "agreement": agreement,
            "n_agents": len(stances),
            "note": None if pairs else "insufficient_agents",
        })
    return results
