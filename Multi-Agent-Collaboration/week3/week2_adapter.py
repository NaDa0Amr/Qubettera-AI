"""Bridge from the Week 3 orchestrator to the merged Week 2 agent runtime."""

from __future__ import annotations

import json
from typing import Any

from .context import render_turn_prompt
from .models import AgentTurnResult, EvidenceItem, TurnRequest


class Week2AgentRuntime:
    """Keep one compiled Week 2 graph alive for the whole discussion.

    Every agent receives a stable thread ID of ``discussion_id:agent_id`` so
    LangGraph checkpoint memory remains separate per agent and continues across
    rounds. The caller can inject a model/tools for testing or use Week 2's
    configured defaults.
    """

    def __init__(self, *, model: Any = None, tools: list | None = None, checkpointer: Any = None):
        from langgraph.checkpoint.memory import MemorySaver

        from src.agent.graph import build_graph

        self.checkpointer = checkpointer or MemorySaver()
        build_kwargs: dict[str, Any] = {"checkpointer": self.checkpointer}
        if model is not None:
            build_kwargs["model"] = model
        if tools is not None:
            build_kwargs["tools"] = tools
        self.graph = build_graph(**build_kwargs)

    def run_turn(self, request: TurnRequest) -> AgentTurnResult:
        from langchain_core.messages import HumanMessage

        from src.personas.loader import load_persona
        from src.utils.agent_utils import extract_opinion

        prompt = self._build_turn_prompt(request)
        graph_input = {
            "task": request.brief.render(),
            "messages": [HumanMessage(content=prompt)],
            "neighbor_opinions": request.neighbor_opinions,
            "persona": dict(load_persona(request.agent_id)),
            "final_opinion": "",
            "retrieved_docs": [],
            "web_documents": [],
            "retrieval_queries": [],
        }
        thread_id = f"{request.discussion_id}:{request.agent_id}"
        state = self.graph.invoke(
            graph_input,
            config={"configurable": {"thread_id": thread_id}},
        )
        opinion = extract_opinion(state).strip()
        if not opinion:
            raise RuntimeError(f"Week 2 agent {request.agent_id!r} returned no final response.")

        runtime_evidence = tuple(
            self._evidence_from_document(document)
            for document in [*state.get("retrieved_docs", []), *state.get("web_documents", [])]
            if isinstance(document, dict)
        )
        return AgentTurnResult(
            response_text=opinion,
            opinion_text=opinion,
            evidence=runtime_evidence,
            retrieval_queries=tuple(str(item) for item in state.get("retrieval_queries", [])),
            metadata={
                "thread_id": thread_id,
                "internal_retrieved_docs": len(state.get("retrieved_docs", [])),
                "internal_web_documents": len(state.get("web_documents", [])),
            },
        )

    @staticmethod
    def _build_turn_prompt(request: TurnRequest) -> str:
        # Task 3: prompt construction is delegated to week3.context so it is
        # covered by its own unit tests and shared with any other runtime.
        return render_turn_prompt(request)

    @staticmethod
    def _evidence_from_document(document: dict[str, Any]) -> EvidenceItem:
        raw_score = document.get("score")
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None
        known = {"text", "title", "url", "source_url", "score"}
        metadata = {key: value for key, value in document.items() if key not in known}
        return EvidenceItem(
            text=str(document.get("text") or ""),
            title=str(document.get("title") or ""),
            url=str(document.get("url") or document.get("source_url") or ""),
            score=score,
            metadata=metadata,
        )
