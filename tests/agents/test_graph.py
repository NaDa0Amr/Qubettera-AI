from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from qubettera.agents.agent.graph import build_graph
from qubettera.agents.personas import load_persona
from qubettera.agents.tools import retrieval_tool


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []
        self.bound_tools = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


def graph_input(prompt="Compare architectures"):
    return {
        "messages": [HumanMessage(content=prompt)],
        "persona": load_persona("moe_efficiency"),
        "retrieved_docs": [],
        "retrieval_queries": [],
    }


def test_react_loop_executes_tool_and_records_normalized_documents(monkeypatch):
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {
                "text": "measured evidence",
                "url": "https://example.test/moe",
                "title": "MoE Study",
                "rrf_score": 0.5,
            }
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "retrieve_knowledge_base",
                        "args": {"query": "MoE active parameter FLOPs", "top_k": 1},
                        "id": "call-1",
                    }
                ],
            ),
            AIMessage(content="Evidence-backed final answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        graph_input(), config={"configurable": {"thread_id": "react-unit"}}
    )

    assert result["retrieval_queries"] == ["MoE active parameter FLOPs"]
    assert result["retrieved_docs"][0]["url"] == "https://example.test/moe"
    assert any(isinstance(message, ToolMessage) for message in result["messages"])
    assert result["messages"][-1].content == "Evidence-backed final answer."


def test_same_thread_accumulates_messages_with_checkpointer():
    model = ScriptedModel([AIMessage(content="first"), AIMessage(content="second")])
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    config = {"configurable": {"thread_id": "memory-unit"}}
    graph.invoke(graph_input("first question"), config=config)
    result = graph.invoke(graph_input("second question"), config=config)

    human_messages = [
        message.content
        for message in result["messages"]
        if isinstance(message, HumanMessage)
    ]
    assert human_messages == ["first question", "second question"]


def test_sixth_turn_generates_summary_and_prompts_with_recent_window():
    history = []
    for index in range(6):
        history.extend(
            [HumanMessage(content=f"question {index}"), AIMessage(content=f"answer {index}")]
        )
    model = ScriptedModel(
        [
            AIMessage(content="Summary preserving question zero."),
            AIMessage(content="new answer"),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        {
            "messages": history,
            "persona": load_persona("moe_efficiency"),
            "retrieved_docs": [],
            "retrieval_queries": [],
        },
        config={"configurable": {"thread_id": "summary-unit"}},
    )

    assert result["memory_summary"] == "Summary preserving question zero."
    assert result["summarized_message_count"] == 2
    ordinary_prompt = model.invocations[-1]
    assert isinstance(ordinary_prompt[0], SystemMessage)
    assert "Summary preserving question zero." in ordinary_prompt[0].content
    assert all(message.content != "question 0" for message in ordinary_prompt[1:])
    assert any(message.content == "question 1" for message in ordinary_prompt[1:])

