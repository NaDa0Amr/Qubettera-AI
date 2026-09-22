"""LangChain @tool wrapper around the direct Supabase+Ollama retrieval backend.

The public interface (knowledge_retrieval) is unchanged from the original
HTTP-based implementation. Only the backend changed: we now call
src.retrieval.search_knowledge_base() directly instead of posting to a
FastAPI server, removing the server dependency entirely.

A structured JSON envelope {"documents": [...], "error": ...} is returned
so the agent and opinion pipeline can parse results without string parsing.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from src.retrieval import search_knowledge_base

logger = logging.getLogger(__name__)


def retrieve(query: str, top_k: int = 5, rerank: bool = False) -> list[dict[str, Any]]:
    """Execute knowledge retrieval via Supabase + Kaggle Ollama."""
    return search_knowledge_base(query=query, top_k=top_k)


def _regenerate_query_with_llm(original_query: str, reason: str = "") -> str | None:
    """Use the LLM to rewrite a query that failed to retrieve relevant documents."""
    try:
        from src.llm.factory import get_chat_model
        from langchain_core.messages import HumanMessage

        model = get_chat_model()
        prompt = (
            "You are an expert retrieval engineer for a technical knowledge base on Transformer architectures.\n"
            f"The search query: '{original_query}' did not return relevant chunks from the database (issue: {reason or 'low similarity / no matches'}).\n"
            "Rewrite it into an effective, concise technical search query (max 6-12 keywords) focusing on "
            "core architecture terms, scaling laws, benchmark metrics, or specific concepts.\n"
            "Return ONLY the new query string, without quotes or conversational filler."
        )
        response = model.invoke([HumanMessage(content=prompt)])
        new_query = str(getattr(response, "content", "")).strip().strip('"\'')
        if new_query and new_query.lower() != original_query.lower():
            return new_query
    except Exception as exc:
        logger.debug("Query regeneration failed: %s", exc)
    return None


@tool
def knowledge_retrieval(query: str, top_k: int = 5, rerank: bool = False) -> str:
    """Search the internal knowledge base (Supabase + Kaggle Ollama) for grounded evidence.

    Use a focused natural-language query. Results contain text, title, source
    URL, and distance score. Returns a JSON string with a 'documents' list.
    Falls back to an error envelope when the service is unreachable.
    """
    try:
        results = retrieve(query, top_k=top_k, rerank=rerank)

        # Check if results are relevant: must be non-empty and have good distance (<= 0.40)
        is_relevant = bool(results) and (
            results[0].get("distance") is None or float(results[0].get("distance", 1.0)) <= 0.40
        )
        query_regenerated = False
        effective_query = query

        if not is_relevant:
            reason = "no chunks found" if not results else f"weak similarity (distance={results[0].get('distance')})"
            logger.info("Retrieval for '%s' returned no/weak relevant chunks (%s). Regenerating query via LLM...", query, reason)
            regenerated = _regenerate_query_with_llm(query, reason=reason)
            if regenerated:
                logger.info("Regenerated retrieval query: '%s' -> '%s'", query, regenerated)
                retry_results = retrieve(regenerated, top_k=top_k, rerank=rerank)
                if retry_results:
                    prev_dist = float(results[0].get("distance", 1.0)) if results and results[0].get("distance") is not None else 1.0
                    new_dist = float(retry_results[0].get("distance", 1.0)) if retry_results[0].get("distance") is not None else 0.0
                    if not results or new_dist <= prev_dist:
                        results = retry_results
                    query_regenerated = True
                    effective_query = regenerated

        documents = []
        for i, r in enumerate(results, start=1):
            score = r.get("rrf_score") or r.get("similarity") or r.get("distance")
            # Log full chunk text without truncation
            text_val = str(r.get("text") or "").strip()
            documents.append(
                {
                    "rank": r.get("rank", i),
                    "text": text_val,
                    "title": str(r.get("title") or ""),
                    "url": str(r.get("source_url") or r.get("url") or ""),
                    "score": float(score) if score is not None else None,
                    "distance": r.get("distance"),
                }
            )

        envelope: dict[str, Any] = {"documents": documents}
        if query_regenerated:
            envelope["query_regenerated"] = True
            envelope["original_query"] = query
            envelope["regenerated_query"] = effective_query

        return json.dumps(envelope, ensure_ascii=False)

    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning("knowledge_retrieval failed: %s: %s", error_type, exc)
        return json.dumps(
            {
                "documents": [],
                "error": f"knowledge base unreachable: {error_type}",
            }
        )


@tool("retrieve_knowledge_base")
def retrieve_knowledge_base(query: str, top_k: int = 5, rerank: bool = False) -> str:
    """Search the internal knowledge base (Supabase + Kaggle Ollama) for grounded evidence."""
    return knowledge_retrieval.invoke({"query": query, "top_k": top_k, "rerank": rerank})


