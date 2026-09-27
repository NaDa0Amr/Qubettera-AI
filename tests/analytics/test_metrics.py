"""Metric and validation checks that do not require external models."""

import io
import json
from pathlib import Path

import pytest

from qubettera.analytics.agreement import measure_agreement
from qubettera.analytics.influence import estimate_influence
from qubettera.analytics.loader import OpinionSnapshot, load_discussion


def test_agreement_uses_pairwise_distances_and_marks_one_agent():
    rows = [
        {"agent_id": "a", "round": 0, "stance": -1},
        {"agent_id": "b", "round": 0, "stance": 0},
        {"agent_id": "c", "round": 0, "stance": 1},
        {"agent_id": "a", "round": 1, "stance": 0.5},
    ]
    result = measure_agreement(rows)
    assert result[0]["agreement"] == pytest.approx(0.3333, abs=0.0001)
    assert result[1]["agreement"] is None
    assert result[1]["note"] == "insufficient_agents"


def test_influence_uses_routed_transitions_and_message_content():
    values = {"a": [0.8, 0.2, 0.6, -0.2], "b": [-0.5, -0.1, 0.0, 0.5]}
    rows = [
        {"agent_id": agent, "round": round_number, "stance": stance}
        for agent, series in values.items()
        for round_number, stance in enumerate(series)
    ]
    snapshots = [
        OpinionSnapshot(agent, round_number, "discussion", "opinion",
                        recipient_ids=(("b",) if agent == "a" else ("a",)),
                        content_text="dense moe layers")
        for agent in values for round_number in range(4)
    ]
    agents, edges = estimate_influence(rows, [("a", "b")], snapshots)
    assert edges[0]["n_transitions"] == 3
    assert edges[0]["lexical_overlap"] == 1.0
    assert edges[0]["influence"] is not None
    assert agents[0]["influence"] == edges[0]["influence"]
    assert agents[1]["influence"] is None

    insufficient, edge_rows = estimate_influence(rows[:2], [("a", "b")], snapshots)
    assert edge_rows[0]["influence"] is None
    assert edge_rows[0]["note"] == "insufficient_transitions"


@pytest.mark.parametrize("change,reason", [
    (lambda events: events.pop(), "completed"),
    (lambda events: events.insert(2, events[1]), "duplicate"),
    (lambda events: events.pop(2), "incomplete"),
    (lambda events: events[1]["message"].update(round_number=None), "invalid"),
])
def test_loader_rejects_bad_logs(monkeypatch, change, reason):
    path = Path(__file__).with_name("example.jsonl")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    change(events)
    payload = "\n".join(json.dumps(event) for event in events)
    original_open = Path.open

    def fake_open(self, *args, **kwargs):
        return io.StringIO(payload) if self == path else original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    with pytest.raises(ValueError, match=reason):
        load_discussion(path)
