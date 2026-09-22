"""Live web search tool for current external evidence."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from ..search.factory import get_search_provider

logger = logging.getLogger(__name__)

# Lazily initialize the provider
_provider: Any = None


def get_provider() -> Any:
    global _provider
    if _provider is None:
        _provider = get_search_provider()
    return _provider

@tool
def live_web_search(query: str) -> str:
    """
    Performs a live search on the web for up-to-date information, recent papers, or news.
    Use this when you need information beyond the internal knowledge base.
    Returns clean, formatted results with source citations.
    """
    try:
        provider = get_provider()
        results = provider.search(query, max_results=5)
        if not results:
            return f"No results found for query: {query}"
        
        formatted = [result.to_markdown(i) for i, result in enumerate(results, 1)]
        return "\n".join(formatted)
    except Exception as e:
        return f"Error performing live search: {str(e)}"