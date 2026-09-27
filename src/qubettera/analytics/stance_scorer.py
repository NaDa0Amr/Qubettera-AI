"""Score each opinion against a fixed proposition using the shared chat model."""

from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass
from typing import Any

from qubettera.agents.llm.factory import get_chat_model


_SYSTEM_PROMPT = (
    "Score the opinion's stance toward the proposition. Return only JSON with "
    'keys "stance" (a number from -1 to 1) and "reasoning" (one sentence). '
    "-1 means strongly opposed, 0 means neutral, and 1 means strongly in favor. "
    "Judge the position expressed, not the tone."
)


@dataclass(frozen=True)
class StanceResult:
    stance: float
    reasoning: str
    samples: tuple[float, ...] = ()


def _median_result(results: list[StanceResult]) -> StanceResult:
    """Use the median score and the reasoning closest to it."""
    if not results:
        raise ValueError("At least one stance result is required")
    median = float(statistics.median(result.stance for result in results))
    closest = min(results, key=lambda result: abs(result.stance - median))
    return StanceResult(median, closest.reasoning, tuple(r.stance for r in results))


def _json_text(raw: str) -> str:
    """Remove one Markdown wrapper without accepting surrounding prose."""
    value = raw.strip()
    if value.startswith("```") and value.endswith("```"):
        value = value[3:-3].strip()
    elif value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    value = re.sub(r"\Ajson\s*\r?\n", "", value, count=1, flags=re.IGNORECASE)
    return value.strip()


class StanceScorer:
    """Reuse the discussion provider with temperature zero for stance scoring."""

    def __init__(
        self,
        model: str | None = None,
        num_samples: int = 1,
        chat_model: Any | None = None,
    ) -> None:
        if num_samples < 1:
            raise ValueError("num_samples must be at least 1")
        self.client = chat_model or get_chat_model(model=model, temperature=0.0)
        self.model = model or getattr(self.client, "model_name", None) or getattr(
            self.client, "model", None
        )
        self.num_samples = num_samples

    def _score_once(self, proposition: str, opinion_text: str, round_number: int) -> StanceResult:
        response = self.client.invoke([
            ("system", _SYSTEM_PROMPT),
            ("human", f"Proposition: {proposition}\nRound: {round_number}\nOpinion:\n{opinion_text}"),
        ])
        raw = response.content
        if not isinstance(raw, str):
            raise ValueError("Stance model returned non-text content")
        try:
            payload = json.loads(_json_text(raw))
            if not isinstance(payload, dict):
                raise ValueError("stance response must be an object")
            if isinstance(payload.get("stance"), bool):
                raise ValueError("stance must be numeric")
            stance = float(payload["stance"])
            if not math.isfinite(stance) or not -1.0 <= stance <= 1.0:
                raise ValueError("stance must be a finite number in [-1, 1]")
            reasoning = str(payload.get("reasoning", ""))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Stance model returned invalid JSON: {raw!r}") from exc
        return StanceResult(stance, reasoning, (stance,))

    def score(self, proposition: str, opinion_text: str, round_number: int) -> StanceResult:
        results = [
            self._score_once(proposition, opinion_text, round_number)
            for _ in range(self.num_samples)
        ]
        return results[0] if len(results) == 1 else _median_result(results)
