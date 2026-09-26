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


def retrieve(
    query: str,
    top_k: int = 5,
    adaptive_expand: bool = False,
) -> list[dict[str, Any]]:
    """Execute Qwen3 + PostgreSQL hybrid retrieval."""
    return retrieve_from_rag(
        query=query,
        top_k=top_k,
        adaptive_expand=adaptive_expand,
    )


@tool
def knowledge_retrieval(
    query: str,
    top_k: int = 5,
    adaptive_expand: bool = False,
) -> str:
    """Search the local Qwen3/PostgreSQL knowledge base for grounded evidence.

    Use a focused natural-language query. Results contain text, title, source
    URL, and distance score. Returns a JSON string with a 'documents' list.
    Falls back to an error envelope when the service is unreachable.
    """
    try:
        retrieval_options = {
            "top_k": top_k,
            "adaptive_expand": adaptive_expand,
        }
        results = retrieve(query, **retrieval_options)

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
        envelope["query_expansion_used"] = any(
            bool(result.get("query_expansion_used")) for result in results
        )
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
def retrieve_knowledge_base(
    query: str,
    top_k: int = 5,
    adaptive_expand: bool = False,
) -> str:
    """Search the local Qwen3/PostgreSQL knowledge base for grounded evidence."""
    return knowledge_retrieval.invoke(
        {
            "query": query,
            "top_k": top_k,
            "adaptive_expand": adaptive_expand,
        }
    )


