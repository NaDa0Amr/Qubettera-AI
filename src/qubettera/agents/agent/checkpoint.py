"""Explicit memory or durable PostgreSQL checkpoint configuration.

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
    """Open the explicitly selected checkpointer.

    Uses PostgresSaver only when ``CHECKPOINT_BACKEND=postgres`` and all
    connection variables are present; missing variables raise an error. RAG settings must
    not silently change agent-memory behavior.
    """
    backend = os.environ.get("CHECKPOINT_BACKEND", "memory").strip().lower()
    if backend not in {"memory", "postgres"}:
        raise ValueError("CHECKPOINT_BACKEND must be memory or postgres.")
    if backend == "postgres":
        missing = [name for name in _REQUIRED_PG_VARS if not os.environ.get(name)]
        if missing:
            raise ValueError("PostgreSQL checkpoints require: " + ", ".join(missing))
        with open_postgres_checkpointer() as saver:
            yield saver
    else:
        from langgraph.checkpoint.memory import MemorySaver

        yield MemorySaver()
