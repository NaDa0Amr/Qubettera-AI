from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveResult(BaseModel):
    rank: int
    chunk_id: Any
    document_id: Any = None
    text: str
    title: str | None = None
    source_url: str | None = None
    url: str | None = None
    topic: str | None = None
    distance: float | None = None
    similarity: float | None = None
    rrf_score: float | None = None


class RetrieveResponse(BaseModel):
    query: str
    top_k: int
    results: list[RetrieveResult]
