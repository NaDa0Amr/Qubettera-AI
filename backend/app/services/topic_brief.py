from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only for type hints; the real import happens lazily below
    from qubettera.discussion.models import DiscussionBrief


def build_brief_from_topic(topic: str) -> "DiscussionBrief":
    # Imported here, not at module top, so the API can boot (and /health can
    # answer) even when Multi-Agent-Collaboration isn't on sys.path yet.
    from qubettera.discussion.models import DiscussionBrief

    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be blank")
    return DiscussionBrief(
        objective=f"Explore the topic below, state where the group agrees or "
        f"disagrees, and reach a well-reasoned collective position: {topic}",
        constraints=(),
        topics=(topic,),
        strict_notes=(
            "Use retrieved evidence for factual claims when evidence is available.",
            "State uncertainty when the available evidence does not settle a claim.",
        ),
    )
