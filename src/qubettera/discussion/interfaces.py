"""Replaceable boundaries used by the orchestrator."""

from __future__ import annotations

from typing import Protocol

from .models import AgentTurnResult, EvidenceItem, TurnRequest


class AgentRuntime(Protocol):
    """Runs one configured Week 2 agent turn."""

    def run_turn(self, request: TurnRequest) -> AgentTurnResult: ...


class RetrievalProvider(Protocol):
    """Task 5 boundary: obtain evidence for the current agent turn."""

    def build_query(self, request: TurnRequest) -> str: ...

    def retrieve(self, query: str, request: TurnRequest) -> tuple[EvidenceItem, ...]: ...


class NoRetrievalProvider:
    """Task 1/2 default used until the Task 5 provider is connected."""

    def build_query(self, request: TurnRequest) -> str:
        return ""

    def retrieve(self, query: str, request: TurnRequest) -> tuple[EvidenceItem, ...]:
        return ()


class EventSink(Protocol):
    """Task 6/7 boundary for logging or persistent storage."""

    def write_event(self, event: dict) -> None: ...


class NullEventSink:
    def write_event(self, event: dict) -> None:
        return None
