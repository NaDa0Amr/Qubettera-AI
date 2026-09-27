"""Memory behavior migrated from JSON files to the active checkpoint runtime."""
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from qubettera.agents.agent.graph import build_graph
from qubettera.agents.personas import load_persona

class Model:
    def invoke(self, messages):
        return AIMessage(content="remembered")


def test_memory_survives_graph_recreation_and_isolates_threads():
    saver = MemorySaver()
    config = {"configurable": {"thread_id": "first-agent"}}
    first = build_graph(checkpointer=saver, model=Model(), tools=[])
    first.invoke({"persona": load_persona("dr_aris"),
                  "messages": [HumanMessage(content="latency budget 50ms p99")]}, config=config)
    second = build_graph(checkpointer=saver, model=Model(), tools=[])
    assert "50ms p99" in str(second.get_state(config).values["messages"])
    assert not second.get_state({"configurable": {"thread_id": "other-agent"}}).values
    state = second.invoke({"messages": [HumanMessage(content="second fact")]}, config=config)
    assert sum(m.type == "human" for m in state["messages"]) == 2
