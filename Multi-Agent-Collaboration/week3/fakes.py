"""Deterministic agent runtime and retrieval provider for local tests/demos."""

from __future__ import annotations

from .models import AgentTurnResult, EvidenceItem, TurnRequest


class DeterministicAgentRuntime:
    """Return predictable responses without API keys or external services."""

    def __init__(self):
        self.requests: list[TurnRequest] = []

    def run_turn(self, request: TurnRequest) -> AgentTurnResult:
        self.requests.append(request)
        senders = [message.sender_id for message in request.incoming_messages]
        context = ", ".join(senders) if senders else "no neighboring messages"
        response = (
            f"{request.agent_id} {request.phase} round {request.round_number}; "
            f"received: {context}."
        )
        return AgentTurnResult(response_text=response, opinion_text=response)


class DeterministicRetrievalProvider:
    """Task 5 stand-in that exercises the retrieval boundary with no external services.

    Useful for the ``--mode fake`` demo and for tests that only need to assert
    *how many times* and *with what query* retrieval was invoked, without
    depending on Supabase/Ollama. ``week3.retrieval_provider.TeamRetrievalProvider``
    is the real implementation used with ``--mode live``.
    """

    def __init__(self):
        self.build_query_calls: list[TurnRequest] = []
        self.retrieve_calls: list[tuple[str, TurnRequest]] = []

    def build_query(self, request: TurnRequest) -> str:
        self.build_query_calls.append(request)
        parts = [request.brief.objective]
        if request.brief.topics:
            parts.append(request.brief.topics[0])
        for message in request.incoming_messages:
            parts.append(f"{message.sender_id}: {message.opinion or message.content}")
        return " | ".join(part for part in parts if part)

    def retrieve(self, query: str, request: TurnRequest) -> tuple[EvidenceItem, ...]:
        self.retrieve_calls.append((query, request))
        return (
            EvidenceItem(
                text=f"Deterministic evidence for: {query}",
                title="Fake Knowledge Base Result",
                url="https://example.org/fake-evidence",
                score=0.1,
            ),
        )
