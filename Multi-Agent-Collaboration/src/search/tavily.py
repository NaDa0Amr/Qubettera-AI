"""Tavily web search provider — direct REST API with optional keyless mode.

Upgraded from the SDK-based implementation to call Tavily's REST API
directly. Supports keyless mode (no TAVILY_API_KEY needed for light
testing) and provides typed WebSearchExecutionError on failure.

Ported from project/Intelligent-Agent-Framework/src/web_search.py.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List

import requests

from .base import SearchProvider, SearchResult

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class WebSearchExecutionError(RuntimeError):
    """Raised when the Tavily search request cannot complete safely."""


class TavilyProvider(SearchProvider):
    """Direct Tavily REST API client with keyless fallback."""

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        return requests.Session()

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        api_key = os.getenv("TAVILY_API_KEY", "").strip() or None
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers["X-Tavily-Access-Mode"] = "keyless"

        payload = {
            "query": " ".join(query.split()),
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        http = self._get_session()
        response: Any | None = None
        try:
            response = http.post(TAVILY_SEARCH_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            status = getattr(response, "status_code", None)
            if status in {401, 403}:
                msg = "Tavily not authorized. Check TAVILY_API_KEY or use keyless mode."
            elif status in {429, 432}:
                msg = "Tavily rate limit reached. Wait and retry, or add a free TAVILY_API_KEY."
            else:
                msg = f"Tavily search failed: {exc}"
            logger.warning(msg)
            raise WebSearchExecutionError(msg) from exc

        results: List[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")
            title = item.get("title") or url
            content = item.get("content", "")
            results.append(SearchResult(title=title, url=url, content=content, snippet=content[:200]))
        return results
