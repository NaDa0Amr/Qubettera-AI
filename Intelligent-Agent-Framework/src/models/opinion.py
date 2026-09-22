"""Structured output dataclass for a single agent opinion generation run.

Ported from project/Intelligent-Agent-Framework/src/agent.py (OpinionResult).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OpinionResult:
    """Captures all outputs from one opinion generation run."""

    agent_id: str
    persona_name: str
    topic: str
    opinion_text: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "persona_name": self.persona_name,
            "topic": self.topic,
            "opinion_text": self.opinion_text,
            "sources": self.sources,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp,
        }


def dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate sources by URL, preserving order."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for source in sources:
        url = source.get("source_url") or source.get("url") or ""
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        result.append(source)
    return result
