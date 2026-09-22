"""Append-only event log used by the Task 2 demo and acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class JsonlEventSink:
    """Write each orchestration event immediately as one JSON line.

    This gives Task 2 an inspectable execution log. Task 6 can replace or
    combine this sink with the team's PostgreSQL persistence implementation.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def write_event(self, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
