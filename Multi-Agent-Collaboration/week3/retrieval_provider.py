"""Task 5: connect the discussion to Week 1's knowledge base during every round.

``TeamRetrievalProvider`` implements the ``RetrievalProvider`` protocol defined
in ``week3/interfaces.py`` and replaces the ``NoRetrievalProvider`` placeholder.
It builds a query from the current discussion state (not just the original
topic) and calls the existing ``src.retrieval.search_knowledge_base`` backend
directly — it does not stand up a second, independent knowledge base.
"""

from __future__ import annotations

import logging
from typing import Any

from src.personas.loader import PersonaConfigError, load_persona
from src.retrieval import (
    RetrievalConfigurationError,
    RetrievalExecutionError,
    search_knowledge_base,
)

from .models import EvidenceItem, TurnRequest

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
_MAX_QUERY_CHARS = 1_800
_MAX_COMPONENT_CHARS = 280


class TeamRetrievalProvider:
    """Real ``RetrievalProvider`` backed by the Week 1 Supabase + Ollama stack.

    One instance is shared across an entire discussion run. The orchestrator
    calls ``build_query``/``retrieve`` once per agent per turn (initial stage
    included), so with 5 agents and 3 rounds this issues at least
    ``5 * 3 = 15`` discussion-round retrieval calls, per the Task 5 acceptance
    test.

    ``ollama_client``/``connection`` are injectable purely for testing;
    production code should leave them unset and configure ``DATABASE_URL`` /
    ``KAGGLE_OLLAMA_URL`` in the repository ``.env`` file instead.
    """

    def __init__(
        self,
        *,
        top_k: int = DEFAULT_TOP_K,
        database_url: str | None = None,
        kaggle_url: str | None = None,
        embedding_model: str | None = None,
        ollama_client: Any = None,
        connection: Any = None,
    ):
        self.top_k = top_k
        self._database_url = database_url
        self._kaggle_url = kaggle_url
        self._embedding_model = embedding_model
        self._ollama_client = ollama_client
        self._connection = connection

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
            results = search_knowledge_base(
                query,
                top_k=self.top_k,
                database_url=self._database_url,
                kaggle_url=self._kaggle_url,
                embedding_model=self._embedding_model,
                ollama_client=self._ollama_client,
                connection=self._connection,
            )
        except (RetrievalConfigurationError, RetrievalExecutionError) as exc:
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