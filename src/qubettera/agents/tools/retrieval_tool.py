"""LangChain tool wrapper around the shared local RAG retrieval backend.

The public interface (knowledge_retrieval) is unchanged from the original
HTTP-based implementation. It calls the shared Qwen3/PostgreSQL retrieval
service directly, removing the API-server dependency.

A structured JSON envelope {"documents": [...], "error": ...} is returned
so the agent and opinion pipeline can parse results without string parsing.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from qubettera.rag.retrieve import retrieve as retrieve_from_rag

logger = logging.getLogger(__name__)

# Minimum cosine similarity for the top result to count as a real match. The
# hybrid retrieval service returns ``similarity`` but never ``distance``, and
# ``rrf_score`` is rank-normalised (it stays flat regardless of match quality),
# so it cannot be used as a relevance signal.
MIN_TOP_SIMILARITY = 0.50


def _top_similarity(results: list[dict[str, Any]]) -> float | None:
    """Return the top result's similarity, or None when unavailable."""
    if not results:
        return None
    raw = results[0].get("similarity")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def retrieve(query: str, top_k: int = 5, rerank: bool = False) -> list[dict[str, Any]]:
    """Execute Qwen3 + PostgreSQL hybrid retrieval."""
    return retrieve_from_rag(query=query, top_k=top_k, rerank=rerank)


def _regenerate_query_with_llm(original_query: str, reason: str = "") -> str | None:
    """Use the LLM to rewrite a query that failed to retrieve relevant documents."""
    try:
        from qubettera.agents.llm.factory import get_chat_model
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
    """Search the local Qwen3/PostgreSQL knowledge base for grounded evidence.

    Use a focused natural-language query. Results contain text, title, source
    URL, and similarity score. Returns a JSON string with a 'documents' list.
    Falls back to an error envelope when the service is unreachable.
    """
    try:
        results = retrieve(query, top_k=top_k, rerank=rerank)

        # Relevance gate: the top hit must clear MIN_TOP_SIMILARITY. Results that
        # carry no similarity are treated as relevant so an unexpected schema
        # change cannot silently disable retrieval.
        top_similarity = _top_similarity(results)
        is_relevant = bool(results) and (top_similarity is None or top_similarity >= MIN_TOP_SIMILARITY)
        query_regenerated = False
        effective_query = query

        if not is_relevant:
            reason = "no chunks found" if not results else f"weak similarity (top={top_similarity:.3f})"
            logger.info("Retrieval for '%s' returned no/weak relevant chunks (%s). Regenerating query via LLM...", query, reason)
            regenerated = _regenerate_query_with_llm(query, reason=reason)
            if regenerated:
                logger.info("Regenerated retrieval query: '%s' -> '%s'", query, regenerated)
                retry_results = retrieve(regenerated, top_k=top_k, rerank=rerank)
                if retry_results:
                    # Higher similarity is better, so only adopt the retry when it
                    # does not make the top match worse.
                    new_similarity = _top_similarity(retry_results)
                    if not results or new_similarity is None or (
                        top_similarity is not None and new_similarity >= top_similarity
                    ):
                        results = retry_results
                    query_regenerated = True
                    effective_query = regenerated

        documents = []
        for i, r in enumerate(results, start=1):
            score = r.get("similarity") or r.get("rrf_score")
            # Log full chunk text without truncation
            text_val = str(r.get("text") or "").strip()
            documents.append(
                {
                    "rank": r.get("rank", i),
                    "text": text_val,
                    "title": str(r.get("title") or ""),
                    "url": str(r.get("source_url") or r.get("url") or ""),
                    "score": float(score) if score is not None else None,
                }
            )

        envelope: dict[str, Any] = {"documents": documents}
        # Expose KB quality so the graph can apply the KB-first web ladder: when
        # the best hit is below MIN_TOP_SIMILARITY the turn is treated as
        # "KB insufficient", which permits live_web_search even though the KB
        # tool round was already spent.
        envelope["top_similarity"] = top_similarity
        envelope["insufficient"] = not is_relevant
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
                # An unreachable KB cannot ground a claim, so the web fallback
                # must be permitted rather than blocked by the spent KB round.
                "insufficient": True,
                "top_similarity": None,
            }
        )


@tool("retrieve_knowledge_base")
def retrieve_knowledge_base(query: str, top_k: int = 5, rerank: bool = False) -> str:
    """Search the local Qwen3/PostgreSQL knowledge base for grounded evidence."""
    return knowledge_retrieval.invoke({"query": query, "top_k": top_k, "rerank": rerank})


