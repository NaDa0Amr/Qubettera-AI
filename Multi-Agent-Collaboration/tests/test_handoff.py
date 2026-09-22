from contextlib import nullcontext

from langchain_core.messages import AIMessage

from src import handoff


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
    monkeypatch.setattr(handoff, "open_postgres_checkpointer", lambda: nullcontext(object()))
    monkeypatch.setattr(handoff, "build_graph", lambda checkpointer: fake_graph)

    result = handoff.get_response("dense_reliability", "dense-thread", "Hello")

    assert result == "handoff response"
    assert fake_graph.config == {"configurable": {"thread_id": "dense-thread"}}
    assert "routing instability" in fake_graph.graph_input["persona"]["retrieval_focus"]

