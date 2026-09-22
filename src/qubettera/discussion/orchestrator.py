"""Task 2: round-by-round discussion orchestration engine."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from collections.abc import Iterator
from typing import Callable
from uuid import uuid4

from .agent_graph import AgentGraph
from .context import select_incoming_messages
from .interfaces import AgentRuntime, EventSink, NoRetrievalProvider, NullEventSink, RetrievalProvider
from .router import get_recipients
from .models import (
    DiscussionConfig,
    DiscussionResult,
    EvidenceItem,
    RoutedMessage,
    TurnRequest,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiscussionExecutionError(RuntimeError):
    """Raised with the partial result when an orchestration step fails."""

    def __init__(self, message: str, partial_result: DiscussionResult):
        super().__init__(message)
        self.partial_result = partial_result


class DiscussionOrchestrator:
    """Coordinate initial opinions and fixed-snapshot discussion rounds.

    Sequence assignment and persisted results are deterministic. Independent
    participants in a stage may execute concurrently.
    During round N, every agent sees only messages routed to it from the complete
    snapshot of stage N-1. Therefore sequential execution does not leak a
    same-round response to agents that happen to run later.
    """

    def __init__(
        self,
        *,
        graph: AgentGraph,
        agent_runtime: AgentRuntime,
        retrieval_provider: RetrievalProvider | None = None,
        event_sink: EventSink | None = None,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
        max_workers: int | None = None,
    ):
        self.graph = graph
        self.agent_runtime = agent_runtime
        self.retrieval_provider = retrieval_provider or NoRetrievalProvider()
        self.event_sink = event_sink or NullEventSink()
        self.id_factory = id_factory or (lambda: str(uuid4()))
        self.clock = clock or _utc_now
        configured_workers = max_workers or int(os.getenv("DISCUSSION_MAX_WORKERS", "5"))
        if configured_workers <= 0:
            raise ValueError("max_workers must be greater than zero.")
        self.max_workers = configured_workers
        self._write_lock = threading.Lock()

    def run(self, config: DiscussionConfig) -> DiscussionResult:
        config.validate()
        self.graph.validate()
        self.graph.validate_participants(config.participant_ids)

        discussion_id = self.id_factory()
        if not discussion_id.strip():
            raise ValueError("Discussion ID factory returned a blank ID.")
        started_at = self.clock()
        messages: list[RoutedMessage] = []
        current_opinions: dict[str, str] = {}
        sequence = 0

        try:
            self._write_event(
                {
                    "event": "discussion_started",
                    "discussion_id": discussion_id,
                    "created_at": started_at,
                    "config": config.to_dict(),
                    "graph": self.graph.to_dict(),
                }
            )

            # Required initial opinion snapshot, separate from rounds 1-3.
            initial_inputs = [(agent_id, (), "") for agent_id in config.participant_ids]
            previous_snapshot = []
            for message in self._execute_stage(
                config=config,
                discussion_id=discussion_id,
                phase="initial",
                round_number=0,
                sequence_start=sequence,
                inputs=initial_inputs,
            ):
                messages.append(message)
                previous_snapshot.append(message)
                current_opinions[message.sender_id] = message.opinion
            sequence += len(initial_inputs)

            # Required discussion rounds. Each uses the preceding complete snapshot.
            for round_number in range(1, config.num_rounds + 1):
                stage_inputs = [
                    (
                        agent_id,
                        select_incoming_messages(previous_snapshot, agent_id),
                        current_opinions[agent_id],
                    )
                    for agent_id in config.participant_ids
                ]
                current_snapshot = []
                for message in self._execute_stage(
                    config=config,
                    discussion_id=discussion_id,
                    phase="discussion",
                    round_number=round_number,
                    sequence_start=sequence,
                    inputs=stage_inputs,
                ):
                    messages.append(message)
                    current_snapshot.append(message)
                    current_opinions[message.sender_id] = message.opinion
                sequence += len(stage_inputs)
                previous_snapshot = current_snapshot

            completed_at = self.clock()
            result = DiscussionResult(
                discussion_id=discussion_id,
                status="completed",
                config=config,
                graph=self.graph.to_dict(),
                messages=tuple(messages),
                started_at=started_at,
                completed_at=completed_at,
            )
            self._write_event(
                {
                    "event": "discussion_completed",
                    "discussion_id": discussion_id,
                    "created_at": completed_at,
                    "message_count": len(messages),
                    "discussion_turn_count": sum(m.phase == "discussion" for m in messages),
                }
            )
            return result
        except Exception as exc:
            # Merge partial results from any mid-round DiscussionExecutionError
            # so the failure report includes all completed turns.
            if isinstance(exc, DiscussionExecutionError):
                partial_from_round = exc.partial_result.messages
                if partial_from_round:
                    messages.extend(partial_from_round)
            failed_at = self.clock()
            partial = DiscussionResult(
                discussion_id=discussion_id,
                status="failed",
                config=config,
                graph=self.graph.to_dict(),
                messages=tuple(messages),
                started_at=started_at,
                completed_at=failed_at,
                error=f"{type(exc).__name__}: {exc}",
            )
            try:
                self._write_event(
                    {
                        "event": "discussion_failed",
                        "discussion_id": discussion_id,
                        "created_at": failed_at,
                        "error": partial.error,
                        "completed_message_count": len(messages),
                    }
                )
            except Exception:
                pass
            raise DiscussionExecutionError(
                f"Discussion {discussion_id} failed after {len(messages)} completed turns: {exc}",
                partial,
            ) from exc

    def _execute_stage(
        self,
        *,
        config: DiscussionConfig,
        discussion_id: str,
        phase: str,
        round_number: int,
        sequence_start: int,
        inputs: list[tuple[str, tuple[RoutedMessage, ...], str]],
    ) -> Iterator[RoutedMessage]:
        def submit_args(index: int, item: tuple[str, tuple[RoutedMessage, ...], str]):
            agent_id, incoming_messages, previous_opinion = item
            return {
                "config": config,
                "discussion_id": discussion_id,
                "phase": phase,
                "round_number": round_number,
                "sequence_number": sequence_start + index + 1,
                "agent_id": agent_id,
                "incoming_messages": incoming_messages,
                "previous_opinion": previous_opinion,
            }

        if self.max_workers == 1 or len(inputs) == 1:
            outcomes = (
                self._execute_turn(**submit_args(index, item))
                for index, item in enumerate(inputs)
            )
            yield from self._persist_outcomes(discussion_id, outcomes)
            return

        else:
            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(inputs)),
                thread_name_prefix="qubettera-agent",
            ) as executor:
                futures = [
                    executor.submit(self._execute_turn, **submit_args(index, item))
                    for index, item in enumerate(inputs)
                ]
                outcomes = (future.result() for future in futures)
                yield from self._persist_outcomes(discussion_id, outcomes)

    def _persist_outcomes(
        self,
        discussion_id: str,
        outcomes,
    ) -> Iterator[RoutedMessage]:
        for message, runtime_metadata in outcomes:
            with self._write_lock:
                self._write_event(
                    {
                        "event": "turn_completed",
                        "discussion_id": discussion_id,
                        "created_at": message.created_at,
                        "message": message.to_dict(),
                        "runtime_metadata": runtime_metadata,
                    }
                )
            yield message

    def _execute_turn(
        self,
        *,
        config: DiscussionConfig,
        discussion_id: str,
        phase: str,
        round_number: int,
        sequence_number: int,
        agent_id: str,
        incoming_messages: tuple[RoutedMessage, ...],
        previous_opinion: str,
    ) -> tuple[RoutedMessage, dict]:
        # Task 4: recipients come only from the Task 1 graph, never a
        # hand-maintained list, so removing an edge removes a recipient here.
        recipients = get_recipients(agent_id, self.graph)
        request = TurnRequest(
            discussion_id=discussion_id,
            phase=phase,  # type: ignore[arg-type]
            round_number=round_number,
            sequence_number=sequence_number,
            agent_id=agent_id,
            recipient_ids=recipients,
            brief=config.brief,
            incoming_messages=incoming_messages,
            previous_opinion=previous_opinion,
        )

        query = self.retrieval_provider.build_query(request)
        evidence = self.retrieval_provider.retrieve(query, request) if query else ()
        request = replace(request, retrieval_query=query, evidence=tuple(evidence))
        turn_result = self.agent_runtime.run_turn(request)

        response = turn_result.response_text.strip()
        opinion = (turn_result.opinion_text or response).strip()
        if not response:
            raise RuntimeError(f"Agent {agent_id!r} returned a blank response.")
        if not opinion:
            raise RuntimeError(f"Agent {agent_id!r} returned a blank opinion.")

        all_evidence = self._dedupe_evidence((*request.evidence, *turn_result.evidence))
        retrieval_queries = tuple(item for item in (query, *turn_result.retrieval_queries) if item)
        message = RoutedMessage(
            message_id=f"{discussion_id}:{sequence_number:04d}",
            discussion_id=discussion_id,
            phase=request.phase,
            round_number=round_number,
            sequence_number=sequence_number,
            sender_id=agent_id,
            recipient_ids=recipients,
            content=response,
            opinion=opinion,
            retrieval_query=" | ".join(dict.fromkeys(retrieval_queries)),
            evidence=all_evidence,
            created_at=self.clock(),
        )
        return message, turn_result.metadata

    def _write_event(self, event: dict) -> None:
        with self._write_lock:
            self.event_sink.write_event(event)

    @staticmethod
    def _dedupe_evidence(items: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
        seen: set[tuple[str, str, str]] = set()
        result: list[EvidenceItem] = []
        for item in items:
            key = (item.url, item.title, item.text)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return tuple(result)
