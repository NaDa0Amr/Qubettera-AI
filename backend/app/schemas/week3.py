from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DiscussRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    participant_ids: list[str] | None = Field(
        default=None,
        description="Persona IDs to include. Defaults to every persona in personas.json.",
    )
    num_rounds: int = Field(default=3, ge=3, description="Week 3 requires at least 3 rounds.")
    mode: Literal["live", "fake"] = Field(
        default="live",
        description=(
            "'fake' uses deterministic stubs (no LLM calls) — useful for "
            "frontend dev before Week 1/2 are wired up."
        ),
    )