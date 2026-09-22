"""Shared records exchanged by Week 3 components.

Keep these records small and provider independent. Tasks 3-7 can consume the
same records without importing LangChain or LangGraph types.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Phase = Literal["initial", "discussion"]


@dataclass(frozen=True)
class DiscussionBrief:
    """Structured event supplied to all participating agents."""

    objective: str
    constraints: tuple[str, ...]
    topics: tuple[str, ...]
    strict_notes: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.objective.strip():
            raise ValueError("Discussion objective must not be blank.")
        if not self.topics:
            raise ValueError("At least one discussion topic is required.")

    def render(self) -> str:
        """Render the event as a stable prompt section."""
        self.validate()
        lines = ["Objective:", self.objective.strip(), "", "Constraints:"]
        lines.extend(f"- {item}" for item in self.constraints)
        lines.extend(["", "Topics to discuss:"])
        lines.extend(f"- {item}" for item in self.topics)
        if self.strict_notes:
            lines.extend(["", "Strict notes:"])
            lines.extend(f"- {item}" for item in self.strict_notes)
        return "\n".join(lines)


@dataclass(frozen=True)
class DiscussionConfig:
    """Reproducible settings for one discussion run."""

    brief: DiscussionBrief
    participant_ids: tuple[str, ...]
    num_rounds: int = 3
    model_config: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.brief.validate()
        if len(self.participant_ids) < 2:
            raise ValueError("A discussion requires at least two agents.")
        if len(set(self.participant_ids)) != len(self.participant_ids):
            raise ValueError("Participant IDs must be unique.")
        if any(not item.strip() for item in self.participant_ids):
            raise ValueError("Participant IDs must not be blank.")
        if self.num_rounds < 3:
            raise ValueError("Week 3 demonstrations require at least three rounds.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceItem:
    """One retrieved passage made visible to an agent."""

    text: str
    title: str = ""
    url: str = ""
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutedMessage:
    """A response with enough metadata to reconstruct routing and order."""

    message_id: str
    discussion_id: str
    phase: Phase
    round_number: int
    sequence_number: int
    sender_id: str
    recipient_ids: tuple[str, ...]
    content: str
    opinion: str
    retrieval_query: str = ""
    evidence: tuple[EvidenceItem, ...] = ()
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TurnRequest:
    """Everything an agent runtime receives for one turn."""

    discussion_id: str
    phase: Phase
    round_number: int
    sequence_number: int
    agent_id: str
    recipient_ids: tuple[str, ...]
    brief: DiscussionBrief
    incoming_messages: tuple[RoutedMessage, ...] = ()
    previous_opinion: str = ""
    retrieval_query: str = ""
    evidence: tuple[EvidenceItem, ...] = ()

    @property
    def neighbor_opinions(self) -> dict[str, str]:
        """Latest routed content keyed by sender for the Week 2 state."""
        return {message.sender_id: message.opinion or message.content for message in self.incoming_messages}


@dataclass(frozen=True)
class AgentTurnResult:
    """Provider-independent result returned by an agent runtime."""

    response_text: str
    opinion_text: str
    evidence: tuple[EvidenceItem, ...] = ()
    retrieval_queries: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscussionResult:
    """Complete in-memory result returned by the orchestrator."""

    discussion_id: str
    status: Literal["completed", "failed"]
    config: DiscussionConfig
    graph: dict[str, Any]
    messages: tuple[RoutedMessage, ...]
    started_at: str
    completed_at: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
