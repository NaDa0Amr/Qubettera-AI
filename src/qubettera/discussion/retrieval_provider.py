"""Connect every discussion round to the shared local RAG knowledge base.

``TeamRetrievalProvider`` builds a query from the current discussion state and
uses the same Qwen3/PostgreSQL retrieval service as the agent workflow.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from qubettera.agents.personas.loader import PersonaConfigError, load_persona
from qubettera.rag.retrieve import RetrievalService

from .models import EvidenceItem, TurnRequest

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
_MAX_QUERY_CHARS = 1_800
_MAX_COMPONENT_CHARS = 280


class TeamRetrievalProvider:
    """Production retrieval provider backed by Qwen3 and PostgreSQL/pgvector.

    One instance is shared across an entire discussion run. The orchestrator
    calls ``build_query``/``retrieve`` once per agent per turn (initial stage
    included), so with 5 agents and 3 rounds this issues at least
    ``5 * 3 = 15`` discussion-round retrieval calls, per the Task 5 acceptance
    test.

    The retrieval service is injectable for tests. Production uses the
    repository's ``PG*`` and embedding settings from ``.env``.
    """

    def __init__(
        self,
        *,
        top_k: int = DEFAULT_TOP_K,
        retrieval_service: RetrievalService | None = None,
    ):
        self.top_k = top_k
        adaptive_expansion = os.environ.get(
            "DISCUSSION_ADAPTIVE_EXPANSION", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._service = retrieval_service or RetrievalService(
            adaptive_expand=adaptive_expansion
        )

    def build_query(self, request: TurnRequest) -> str:
        """Build a focused query from the current discussion state.

        Inputs: the objective, the leading constraint/topic, the agent's
        persona ``retrieval_focus``, its previous opinion, and the messages
        *actually routed* to it this round. ``request.incoming_messages`` is
        already filtered by Task 3/4 (see ``week3.context.select_incoming_messages``),
        so messages hidden by the graph never reach this query.

        Each component is truncated *individually* before being joined - real
        agent responses can run to thousands of characters, and truncating
        only the final joined string would let one long component (typically
        the agent's own previous opinion) crowd out everything after it,
        silently dropping the routed neighbor messages this method exists to
        surface.
        """
        def _clip(text: str) -> str:
            text = text.strip()
            return text if len(text) <= _MAX_COMPONENT_CHARS else text[:_MAX_COMPONENT_CHARS].rsplit(" ", 1)[0] + "..."

        parts: list[str] = [_clip(request.brief.objective)]
        if request.brief.topics:
            parts.append(_clip(request.brief.topics[0]))
        if request.brief.constraints:
            parts.append(_clip(request.brief.constraints[0]))

        try:
            persona = load_persona(request.agent_id)
            if persona.retrieval_focus:
                parts.append(_clip(persona.retrieval_focus))
        except PersonaConfigError:
            # No persona on disk for this agent ID (e.g. in a unit test) -
            # fall back to whatever the brief and messages already provide.
            pass

        if request.previous_opinion:
            parts.append(_clip(request.previous_opinion))

        for message in request.incoming_messages:
            claim = (message.opinion or message.content).strip()
            if claim:
                parts.append(f"{message.sender_id}: {_clip(claim)}")

        query = " | ".join(part for part in parts if part)
        return query[:_MAX_QUERY_CHARS]

    def retrieve(self, query: str, request: TurnRequest) -> tuple[EvidenceItem, ...]:
        if not query.strip():
            return ()
        try:
            results = self._service.retrieve(query, top_k=self.top_k)
        except (RuntimeError, ValueError) as exc:
            # A retrieval outage should not take down the whole discussion; the
            # agent still gets its persona, previous opinion, and routed
            # messages, just no fresh evidence for this one turn.
            logger.warning(
                "discussion %s round %s agent %s: retrieval unavailable (%s)",
                request.discussion_id,
                request.round_number,
                request.agent_id,
                exc,
            )
            return ()

        return tuple(self._to_evidence(item) for item in results)

    @staticmethod
    def _to_evidence(document: dict[str, Any]) -> EvidenceItem:
        known = {"text", "title", "url", "source_url", "score", "distance"}
        metadata = {key: value for key, value in document.items() if key not in known}
        raw_score = document.get("distance", document.get("score"))
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None
        return EvidenceItem(
            text=str(document.get("text") or ""),
            title=str(document.get("title") or ""),
            url=str(document.get("source_url") or document.get("url") or ""),
            score=score,
            metadata=metadata,
        )
