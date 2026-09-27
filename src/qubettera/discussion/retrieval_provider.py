"""Connect every discussion round to the shared local RAG knowledge base.

``TeamRetrievalProvider`` builds a query from the current discussion state and
uses the same Qwen3/PostgreSQL retrieval service as the agent workflow.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import Future
from typing import Any

from qubettera.agents.personas.loader import PersonaConfigError, load_persona
from qubettera.rag.retrieve import RetrievalService

from .models import EvidenceItem, TurnRequest

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
_MAX_QUERY_CHARS = 512


class TeamRetrievalProvider:
    """Production retrieval provider backed by Qwen3 and PostgreSQL/pgvector.

    One instance is shared across an entire discussion run. The orchestrator
    calls ``build_query``/``retrieve`` once per agent per turn (initial stage
    included). A run-local cache shares successful results and in-flight
    requests; backend failures never become cached empty evidence.

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
        self._lock = threading.Lock()
        self._cache = {}
        self._local = threading.local()
        adaptive_expansion = os.environ.get(
            "DISCUSSION_ADAPTIVE_EXPANSION", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.adaptive_expansion = adaptive_expansion
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
        parts = [request.brief.objective]
        try:
            focus = load_persona(request.agent_id).retrieval_focus
            if focus:
                parts.append(focus)
        except PersonaConfigError:
            pass
        if request.previous_opinion:
            parts.append(request.previous_opinion)
        parts.extend(f"{m.sender_id}: {m.opinion or m.content}" for m in request.incoming_messages)
        parts.extend(request.brief.topics[:1])
        parts.extend(request.brief.constraints[:1])
        parts = [" ".join(part.split()) for part in parts if part.strip()]
        # Fair allocation prevents a long brief or previous opinion displacing focus/claims.
        remaining = _MAX_QUERY_CHARS - 3 * (len(parts) - 1)
        if remaining < len(parts):
            parts = parts[:32]
            remaining = _MAX_QUERY_CHARS - 3 * (len(parts) - 1)
        allocations = [0] * len(parts)
        while remaining and any(allocations[i] < len(part) for i, part in enumerate(parts)):
            for i, part in enumerate(parts):
                if remaining and allocations[i] < len(part):
                    allocations[i] += 1
                    remaining -= 1
        return " | ".join(part[:size] for part, size in zip(parts, allocations))

    def begin_run(self):
        with self._lock:
            self._cache.clear()

    def end_run(self):
        self.begin_run()

    def take_warnings(self):
        warnings = getattr(self._local, "warnings", ())
        self._local.warnings = ()
        return warnings

    def retrieve(self, query: str, request: TurnRequest) -> tuple[EvidenceItem, ...]:
        self._local.warnings = ()
        normalized = " ".join(query.split())
        if not normalized:
            return ()
        key = (normalized.casefold(), self.top_k, self.adaptive_expansion)
        with self._lock:
            future = self._cache.get(key)
            owner = future is None
            if owner:
                future = Future()
                self._cache[key] = future
        if owner:
            try:
                rows = self._service.retrieve(normalized, top_k=self.top_k)
                future.set_result(tuple(self._to_evidence(item) for item in rows))
            except Exception as exc:
                future.set_exception(exc)
                with self._lock:
                    self._cache.pop(key, None)
        try:
            return future.result()
        except Exception as exc:
            warning = f"Retrieval unavailable ({type(exc).__name__}); no fresh internal evidence."
            self._local.warnings = (warning,)
            logger.warning("discussion %s agent %s: %s", request.discussion_id, request.agent_id, warning,
                           exc_info=True)
            return ()

    @staticmethod
    def _to_evidence(document: dict[str, Any]) -> EvidenceItem:
        known = {"text", "title", "url", "source_url", "score"}
        metadata = {key: value for key, value in document.items() if key not in known}
        raw_score = document.get("score")
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
