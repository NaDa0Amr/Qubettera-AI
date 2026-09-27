from contextlib import nullcontext

from langchain_core.messages import AIMessage

from qubettera.agents import handoff
import json
import pytest


class FakeGraph:
    def __init__(self):
        self.graph_input = None
        self.config = None

    def invoke(self, graph_input, config):
        self.graph_input = graph_input
        self.config = config
        return {"messages": [AIMessage(content="handoff response")]}


def test_handoff_hides_graph_state_and_loads_requested_persona(monkeypatch):
    fake_graph = FakeGraph()
    monkeypatch.setattr(handoff, "get_checkpointer", lambda: nullcontext(object()))
    monkeypatch.setattr(handoff, "build_graph", lambda checkpointer: fake_graph)

    result = handoff.get_response("dense_reliability", "dense-thread", "Hello")

    assert result == "handoff response"
    assert fake_graph.config == {"configurable": {"thread_id": "dense-thread"}}
    assert "routing instability" in fake_graph.graph_input["persona"]["retrieval_focus"]


def test_neighbor_validation_uses_directed_incoming_edges(monkeypatch, tmp_path):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"nodes": ["dr_aris", "prof_elena", "grad_student"],
        "edges": [["dr_aris", "prof_elena"], ["prof_elena", "grad_student"], ["grad_student", "dr_aris"]]}))
    fake = FakeGraph()
    monkeypatch.setattr(handoff, "get_checkpointer", lambda: nullcontext(object()))
    monkeypatch.setattr(handoff, "build_graph", lambda checkpointer: fake)
    handoff.get_response("dr_aris", "thread", "Question", topology_path=path,
                         neighbor_opinions={"grad_student": "Allowed"})
    with pytest.raises(ValueError, match="non-adjacent"):
        handoff.get_response("dr_aris", "thread", "Question", topology_path=path,
                             neighbor_opinions={"prof_elena": "Wrong direction"})

