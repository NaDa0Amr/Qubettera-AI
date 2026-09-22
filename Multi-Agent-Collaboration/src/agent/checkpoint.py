"""Durable PostgreSQL checkpointer with MemorySaver fallback.

Ported from N/week2-agent/src/agent/checkpoint.py and adapted to be
optional: if Postgres env vars are missing, falls back to in-memory.

Usage:
    with get_checkpointer() as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = graph.invoke(...)
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv

load_dotenv()

_REQUIRED_PG_VARS = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")


def _postgres_available() -> bool:
    """Return True only when all required Postgres env vars are set."""
    return all(os.environ.get(v) for v in _REQUIRED_PG_VARS)


def _make_conninfo() -> str:
    """Build a psycopg connection string from PG* environment variables."""
    from psycopg.conninfo import make_conninfo  # type: ignore[import]

    return make_conninfo(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        connect_timeout="10",
    )


@contextmanager
def open_postgres_checkpointer(conninfo: str | None = None) -> Iterator:
    """Open and initialise a durable LangGraph PostgresSaver.

    Requires langgraph-checkpoint-postgres and PGHOST/PGDATABASE/PGUSER/
    PGPASSWORD in environment. Calls saver.setup() once to ensure the
    checkpoint schema exists.
    """
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import]

    with PostgresSaver.from_conn_string(conninfo or _make_conninfo()) as saver:
        saver.setup()
        yield saver


@contextmanager
def get_checkpointer() -> Iterator:
    """Return the best available checkpointer.

    Uses PostgresSaver when Postgres env vars are present, otherwise falls
    back to MemorySaver (no persistence across restarts).
    """
    if _postgres_available():
        with open_postgres_checkpointer() as saver:
            yield saver
    else:
        from langgraph.checkpoint.memory import MemorySaver

        yield MemorySaver()
