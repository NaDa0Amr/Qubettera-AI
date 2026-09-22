"""Direct Supabase + Kaggle Ollama retrieval backend.

Ported from project/Intelligent-Agent-Framework/src/retrieval.py.
This module replaces the HTTP FastAPI client with a direct connection
to Supabase pgvector using the Ollama embedding service on Kaggle.

Environment variables required:
    DATABASE_URL       — Supabase PostgreSQL connection string
    KAGGLE_OLLAMA_URL  — Ollama service URL (ngrok tunnel from Kaggle notebook)
    EMBEDDING_MODEL    — model name (default: qwen3-embedding:8b)
"""

from __future__ import annotations


import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:8b"
DEFAULT_TOP_K = 5
MAX_TOP_K = 20


class RetrievalConfigurationError(RuntimeError):
    """Raised when required Week 1 connection configuration is missing."""


class RetrievalExecutionError(RuntimeError):
    """Raised when query embedding or database retrieval cannot complete."""


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


def _resolve_top_k(top_k: int | None) -> int:
    if top_k is None:
        raw_value = os.getenv("RETRIEVAL_TOP_K", str(DEFAULT_TOP_K))
        try:
            top_k = int(raw_value)
        except ValueError as exc:
            raise RetrievalConfigurationError(
                "RETRIEVAL_TOP_K must be an integer."
            ) from exc
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("top_k must be an integer")
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
    return top_k


def _response_value(response: Any, key: str) -> Any:
    if isinstance(response, Mapping):
        return response.get(key)
    return getattr(response, key, None)


def _embed_query(client: Any, model: str, query: str) -> list[float]:
    """Generate one query vector using the current or legacy Ollama SDK API."""

    current_api_error: Exception | None = None
    if hasattr(client, "embed"):
        try:
            response = client.embed(model=model, input=query)
            embeddings = _response_value(response, "embeddings")
            if embeddings and isinstance(embeddings, (list, tuple)):
                first = embeddings[0]
                if isinstance(first, (list, tuple)):
                    return [float(value) for value in first]
        except Exception as exc:  # noqa: BLE001 - SDK errors vary by version.
            current_api_error = exc

    # Compatibility with the API used by the original Week 1 test.
    if hasattr(client, "embeddings"):
        try:
            response = client.embeddings(model=model, prompt=query)
            embedding = _response_value(response, "embedding")
            if embedding and isinstance(embedding, (list, tuple)):
                return [float(value) for value in embedding]
        except Exception as exc:
            raise RetrievalExecutionError(
                "The Kaggle Ollama service could not embed the query. Confirm "
                "that its notebook is running and its tunnel URL is current."
            ) from exc

    error = RetrievalExecutionError(
        "The embedding service returned no usable query vector. Confirm that "
        "the Kaggle Ollama notebook is running with qwen3-embedding:8b."
    )
    if current_api_error is not None:
        raise error from current_api_error
    raise error


def _metadata_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _create_ollama_client(kaggle_url: str) -> Any:
    try:
        import ollama
    except ImportError as exc:  # pragma: no cover - dependency installation issue
        raise RetrievalConfigurationError(
            "Missing dependency 'ollama'. Run: "
            "python -m pip install -r requirements.txt"
        ) from exc
    return ollama.Client(host=kaggle_url, timeout=45.0)


def _create_database_connection(database_url: str) -> Any:
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - dependency installation issue
        raise RetrievalConfigurationError(
            "Missing dependency 'psycopg2-binary'. Run: "
            "python -m pip install -r requirements.txt"
        ) from exc
    return psycopg2.connect(database_url, connect_timeout=15)


def search_knowledge_base(
    query: str,
    top_k: int | None = None,
    *,
    database_url: str | None = None,
    kaggle_url: str | None = None,
    embedding_model: str | None = None,
    ollama_client: Any | None = None,
    connection: Any | None = None,
) -> list[dict[str, Any]]:
    """Return ranked Week 1 chunks and source metadata for a natural-language query.

    ``ollama_client`` and ``connection`` are injectable so unit tests can run
    without contacting Kaggle or Supabase. Normal application code should omit
    them and configure the connections in the repository-root ``.env`` file.
    """

    _load_project_environment()
    cleaned_query = _clean_query(query)
    resolved_top_k = _resolve_top_k(top_k)
    database_url = database_url or os.getenv("DATABASE_URL")
    kaggle_url = kaggle_url or os.getenv("KAGGLE_OLLAMA_URL")
    embedding_model = (
        embedding_model or os.getenv("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    )

    if connection is None and not database_url:
        raise RetrievalConfigurationError(
            "DATABASE_URL is missing from the repository-root .env file."
        )
    if ollama_client is None and not kaggle_url:
        raise RetrievalConfigurationError(
            "KAGGLE_OLLAMA_URL is missing from the repository-root .env file."
        )

    owns_connection = connection is None
    try:
        client = ollama_client or _create_ollama_client(str(kaggle_url))
        vector = _embed_query(client, embedding_model, cleaned_query)
        if not vector:
            raise RetrievalExecutionError("The query embedding was empty.")

        vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
        connection = connection or _create_database_connection(str(database_url))

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT chunk_id,
                       document_id,
                       text,
                       metadata,
                       embedding <=> %s::vector AS distance
                FROM chunks
                ORDER BY distance ASC
                LIMIT %s
                """,
                (vector_literal, resolved_top_k),
            )
            rows = cursor.fetchall()
    except (RetrievalConfigurationError, RetrievalExecutionError, ValueError):
        raise
    except Exception as exc:
        raise RetrievalExecutionError(
            "Knowledge-base retrieval failed. Check that the Kaggle Ollama "
            "notebook is running, KAGGLE_OLLAMA_URL is current, and DATABASE_URL "
            "connects to the shared Supabase database."
        ) from exc
    finally:
        if owns_connection and connection is not None:
            connection.close()

    results: list[dict[str, Any]] = []
    for rank, (chunk_id, document_id, text, metadata_value, distance) in enumerate(
        rows, start=1
    ):
        metadata = _metadata_dict(metadata_value)
        source_url = (
            metadata.get("canonical_url")
            or metadata.get("source_url")
            or metadata.get("url")
        )
        results.append(
            {
                "rank": rank,
                "tool": "search_knowledge_base",
                "chunk_id": chunk_id,
                "document_id": document_id,
                "text": text,
                "title": metadata.get("title"),
                "source_url": source_url,
                "topic": metadata.get("topic"),
                "distance": float(distance),
                "metadata": metadata,
            }
        )
    return results
