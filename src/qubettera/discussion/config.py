"""Load the reproducible Week 3 discussion configuration."""

from __future__ import annotations

import json
from pathlib import Path

from .models import DiscussionBrief, DiscussionConfig


def load_discussion_config(path: str | Path) -> DiscussionConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    brief_payload = payload["brief"]
    config = DiscussionConfig(
        brief=DiscussionBrief(
            objective=brief_payload["objective"],
            constraints=tuple(brief_payload.get("constraints", [])),
            topics=tuple(brief_payload["topics"]),
            strict_notes=tuple(brief_payload.get("strict_notes", [])),
        ),
        participant_ids=tuple(payload["participant_ids"]),
        num_rounds=int(payload.get("num_rounds", 3)),
        model_config=dict(payload.get("model_config", {})),
    )
    config.validate()
    return config
