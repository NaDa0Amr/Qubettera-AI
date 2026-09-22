"""File-backed persistent memory for individual agents.

Ported from project/Intelligent-Agent-Framework/src/memory.py.
Each agent gets its own JSON file at outputs/memory/<agent_id>.json.
Survives process restarts unlike LangGraph's in-memory MemorySaver.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_DIR = PROJECT_ROOT / "outputs" / "memory"


@dataclass(frozen=True)
class MemoryEntry:
    timestamp: str
    kind: str
    topic: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp,
            "kind": self.kind,
            "topic": self.topic,
            "content": self.content,
        }


class AgentMemory:
    """Append-only, file-backed memory for one agent."""

    def __init__(self, agent_id: str, *, memory_dir: Path | None = None) -> None:
        self.agent_id = agent_id
        self._dir = memory_dir or DEFAULT_MEMORY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{agent_id}.json"

    def add(self, *, kind: str, topic: str, content: str) -> MemoryEntry:
        """Append one interaction and persist it immediately."""
        entry = MemoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            topic=topic,
            content=content,
        )
        entries = self._read_all()
        entries.append(entry.to_dict())
        self._path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return entry

    def all_entries(self) -> list[MemoryEntry]:
        return [MemoryEntry(**raw) for raw in self._read_all()]

    def recent(self, limit: int = 10) -> list[MemoryEntry]:
        entries = self.all_entries()
        return entries[-limit:]

    def _read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []
