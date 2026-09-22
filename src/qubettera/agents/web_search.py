"""Structured web-search tool for current external evidence.

Tavily's direct Search API is used because it returns ranked titles, URLs,
snippets, and relevance scores. Light testing can use Tavily's official keyless
mode; setting TAVILY_API_KEY uses the account's quota without changing output.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 5
MAX_RESULTS_LIMIT = 10


class WebSearchConfigurationError(RuntimeError):
    """Raised when web-search configuration is invalid."""


class WebSearchExecutionError(RuntimeError):
    """Raised when the web-search request cannot complete safely."""


def _load_project_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def _clean_query(query: str) -> str:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    cleaned = " ".join(query.split())
    if not cleaned:
        raise ValueError("query must not be empty")
    if len(cleaned) > 2_000:
        raise ValueError("query must be 2,000 characters or fewer")
    return cleaned


def _resolve_max_results(max_results: int | None) -> int:
    if max_results is None:
        raw_value = os.getenv("WEB_SEARCH_MAX_RESULTS", str(DEFAULT_MAX_RESULTS))
        try:
            max_results = int(raw_value)
        except ValueError as exc:
            raise WebSearchConfigurationError(
                "WEB_SEARCH_MAX_RESULTS must be an integer."
            ) from exc
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        raise TypeError("max_results must be an integer")
    if not 1 <= max_results <= MAX_RESULTS_LIMIT:
        raise ValueError(f"max_results must be between 1 and {MAX_RESULTS_LIMIT}")
    return max_results


def _create_http_session() -> requests.Session:
    return requests.Session()


def search_web(
    query: str,
    max_results: int | None = None,
    *,
    api_key: str | None = None,
    session: Any | None = None,
) -> list[dict[str, Any]]:
    """Return ranked live-web evidence with titles, snippets, URLs, and scores."""

    _load_project_environment()
    cleaned_query = _clean_query(query)
    resolved_max_results = _resolve_max_results(max_results)
    api_key = api_key if api_key is not None else os.getenv("TAVILY_API_KEY", "")
    api_key = api_key.strip() or None

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"

    payload = {
        "query": cleaned_query,
        "search_depth": "basic",
        "max_results": resolved_max_results,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }

    http = session or _create_http_session()
    response: Any | None = None
    try:
        response = http.post(
            TAVILY_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        status_code = getattr(response, "status_code", None)
        if status_code in {401, 403}:
            message = (
                "Web search was not authorized. Check TAVILY_API_KEY, or leave "
                "it blank to use official keyless mode."
            )
        elif status_code in {429, 432}:
            message = (
                "The Tavily keyless/account search limit was reached. Wait and "
                "retry, or add a free TAVILY_API_KEY to .env."
            )
        else:
            message = (
                "Web search failed. Check the internet connection and Tavily "
                "service availability."
            )
        raise WebSearchExecutionError(message) from exc

    if not isinstance(data, dict):
        raise WebSearchExecutionError("Web search returned an invalid response.")
    raw_results = data.get("results", [])
    if not isinstance(raw_results, list):
        raise WebSearchExecutionError(
            "Web search returned an invalid results collection."
        )

    results: list[dict[str, Any]] = []
    for item in raw_results[:resolved_max_results]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        score = item.get("score")
        results.append(
            {
                "rank": len(results) + 1,
                "tool": "search_web",
                "title": item.get("title") or url,
                "snippet": item.get("content") or "",
                "url": url,
                "score": float(score) if isinstance(score, (int, float)) else None,
                "published_date": item.get("published_date"),
            }
        )
    return results
