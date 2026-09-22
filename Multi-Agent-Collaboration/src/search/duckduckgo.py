"""DuckDuckGo live web search provider."""

from __future__ import annotations

import logging
from typing import List

from .base import SearchProvider, SearchResult

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None
    logging.warning("ddgs (duckduckgo-search) not installed. DuckDuckGo provider will not work.")

class DuckDuckGoProvider(SearchProvider):
    def __init__(self):
        if DDGS is None:
            raise ImportError("Please install duckduckgo-search: pip install duckduckgo-search")
        self._client = DDGS()

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        results = []
        try:
            # Use text search with max_results
            for item in self._client.text(query, max_results=max_results):
                title = item.get("title", "Untitled")
                url = item.get("href", "")
                body = item.get("body", "")
                # Clean body: remove excessive whitespace
                body = " ".join(body.split())
                # Create result
                results.append(SearchResult(title, url, body, body[:200]))
        except Exception as e:
            logging.error(f"DuckDuckGo search failed: {e}")
            # Return empty list on error, tool will handle gracefully
        return results