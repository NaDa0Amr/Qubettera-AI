"""Unified test defaults isolated from a developer's local .env file."""

import pytest


@pytest.fixture(autouse=True)
def stable_agent_defaults(monkeypatch):
    monkeypatch.setenv("RECENT_EXCHANGES_TO_KEEP", "5")
    monkeypatch.setenv("CHECKPOINT_BACKEND", "memory")

