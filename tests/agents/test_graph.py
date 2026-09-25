from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

import pytest

from qubettera.agents.agent.graph import build_graph, max_tool_rounds_per_turn
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


def test_tool_rounds_used_is_tracked_and_exhausts_the_budget(monkeypatch):
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/a", "title": "Study"}
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
            ),
            AIMessage(content="Grounded answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        graph_input(), config={"configurable": {"thread_id": "budget-unit"}}
    )

    assert result["tool_rounds_used"] == 1


def test_spent_tool_budget_on_a_non_final_round_does_not_claim_finality(monkeypatch):
    # Regression test: the tool budget and the "this is the final synthesis"
    # framing used to be the same flag. Because state is checkpointed across a
    # discussion, a single tool round in round 0 marked every later turn as
    # final, so intermediate rounds stopped retrieving and announced a final
    # recommendation.
    monkeypatch.setattr(retrieval_tool, "retrieve", lambda query, top_k, rerank: [])
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q2"}, "id": "c2"}],
            ),
            AIMessage(content="Intermediate answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    graph.invoke(
        {
            "messages": [HumanMessage(content="Compare architectures")],
            "persona": load_persona("moe_efficiency"),
            "retrieved_docs": [],
            "retrieval_queries": [],
            "tool_rounds_used": 1,
            "max_tool_rounds": 1,
            "final_round": False,
        },
        config={"configurable": {"thread_id": "non-final-unit"}},
    )

    system_prompt = model.invocations[0][0]
    assert isinstance(system_prompt, SystemMessage)
    assert "final comprehensive persona recommendation" not in system_prompt.content
    assert "This is not the final round." in system_prompt.content


def test_final_round_keeps_the_final_synthesis_framing(monkeypatch):
    monkeypatch.setattr(retrieval_tool, "retrieve", lambda query, top_k, rerank: [])
    model = ScriptedModel([AIMessage(content="Final answer.")])
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    graph.invoke(
        {
            "messages": [HumanMessage(content="Compare architectures")],
            "persona": load_persona("moe_efficiency"),
            "retrieved_docs": [],
            "retrieval_queries": [],
            "tool_rounds_used": 1,
            "max_tool_rounds": 1,
            "final_round": True,
        },
        config={"configurable": {"thread_id": "final-unit"}},
    )

    system_prompt = model.invocations[0][0].content
    assert "final comprehensive persona recommendation" in system_prompt


def test_fresh_turn_still_requires_retrieval_even_on_the_final_round(monkeypatch):
    # The mandatory-retrieval instruction must win over the finality framing:
    # the last round is the one where an agent most needs fresh evidence.
    monkeypatch.setattr(retrieval_tool, "retrieve", lambda query, top_k, rerank: [])
    model = ScriptedModel([AIMessage(content="Final answer.")])
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    graph.invoke(
        {
            "messages": [HumanMessage(content="Compare architectures")],
            "persona": load_persona("moe_efficiency"),
            "retrieved_docs": [],
            "retrieval_queries": [],
            "tool_rounds_used": 0,
            "max_tool_rounds": 1,
            "final_round": True,
        },
        config={"configurable": {"thread_id": "final-fresh-unit"}},
    )

    system_prompt = model.invocations[0][0].content
    # Both instructions coexist: retrieve this round, then synthesize.
    assert "MANDATORY" in system_prompt
    assert "final comprehensive persona recommendation" in system_prompt
    assert "This is not the final round." not in system_prompt


def test_default_final_round_is_true_for_standalone_runs(monkeypatch):
    # handoff.py and the opinion pipeline build their own graph_input without
    # the discussion keys; those single-shot runs must keep the previous
    # final-synthesis wording once their tool budget is spent.
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/s", "title": "Study"}
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
            ),
            AIMessage(content="Standalone answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    graph.invoke(
        {
            "messages": [HumanMessage(content="Compare architectures")],
            "persona": load_persona("moe_efficiency"),
            "retrieved_docs": [],
            "retrieval_queries": [],
        },
        config={"configurable": {"thread_id": "standalone-unit"}},
    )

    # First call: budget unspent, so retrieval is mandatory.
    assert "MANDATORY" in model.invocations[0][0].content
    # Second call: budget spent, and a standalone run is final by default.
    assert "final comprehensive persona recommendation" in model.invocations[1][0].content


def test_tool_budget_is_reusable_on_a_fresh_turn(monkeypatch):
    # A mid-discussion turn resets tool_rounds_used to 0, so retrieval is
    # available again even though the same agent already spent its budget.
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/b", "title": "Study"}
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
            ),
            AIMessage(content="First turn answer."),
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q2"}, "id": "c2"}],
            ),
            AIMessage(content="Second turn answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    config = {"configurable": {"thread_id": "reset-unit"}}
    graph.invoke(graph_input("first question"), config=config)
    result = graph.invoke(
        {
            **graph_input("second question"),
            "tool_rounds_used": 0,
            "max_tool_rounds": 1,
            "final_round": False,
        },
        config=config,
    )

    assert result["tool_rounds_used"] == 1
    assert result["retrieval_queries"] == ["q2"]


def test_max_tool_rounds_per_turn_validates_env(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_ROUNDS", "2")
    assert max_tool_rounds_per_turn() == 2
    monkeypatch.setenv("MAX_TOOL_ROUNDS", "0")
    assert max_tool_rounds_per_turn() == 0
    monkeypatch.setenv("MAX_TOOL_ROUNDS", "not-a-number")
    with pytest.raises(RuntimeError, match="must be an integer"):
        max_tool_rounds_per_turn()
    monkeypatch.setenv("MAX_TOOL_ROUNDS", "-1")
    with pytest.raises(RuntimeError, match="zero or greater"):
        max_tool_rounds_per_turn()


def test_mandatory_retrieval_backstop_fires_when_evidence_was_prefilled(monkeypatch):
    # The discussion adapter pre-fills retrieved_docs with provider evidence on
    # every turn. Guarding the backstop on an empty retrieved_docs disabled it
    # for every round after the first, which is why rounds 1-3 gathered no tool
    # evidence. Only the per-turn tool budget may gate it.
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "tool evidence", "url": "https://example.test/t", "title": "Tool Study"}
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(content="Answer without tools."),
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
            ),
            AIMessage(content="Grounded answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Compare architectures")],
            "persona": load_persona("moe_efficiency"),
            "task": "Recommend a Transformer architecture for the team.",
            # Pre-filled provider evidence, as a real discussion turn supplies.
            "retrieved_docs": [
                {"text": "provider evidence", "url": "https://example.test/p", "title": "P"}
            ],
            "retrieval_queries": [],
            "tool_rounds_used": 0,
            "max_tool_rounds": 1,
            "final_round": False,
        },
        config={"configurable": {"thread_id": "backstop-unit"}},
    )

    # The retry nudge must be issued and must land as a tool call.
    assert any("MANDATORY STEP" in str(m.content) for m in model.invocations[1])
    assert result["retrieval_queries"] == ["q"]
    # A mid-discussion turn must not be told to present a closing position.
    # The negation itself must avoid the words "final recommendation", or it
    # primes the very heading it is trying to suppress.
    prompt = model.invocations[1][0].content
    assert "This is not the final round." in prompt
    assert "closing team position" in prompt
    assert "final recommendation" not in prompt


def test_backstop_does_not_fire_when_no_tools_are_bound(monkeypatch):
    # ``--no-agent-tools`` compiles the graph with an empty tool registry. The
    # backstop cannot succeed there, so it must not burn an extra model call.
    monkeypatch.setattr(retrieval_tool, "retrieve", lambda query, top_k, rerank: [])
    model = ScriptedModel([AIMessage(content="Answer without tools.")])
    graph = build_graph(checkpointer=InMemorySaver(), model=model, tools=[])
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="Compare architectures")],
            "persona": load_persona("moe_efficiency"),
            "task": "Recommend a Transformer architecture.",
            "retrieved_docs": [
                {"text": "provider evidence", "url": "https://example.test/p", "title": "P"}
            ],
            "retrieval_queries": [],
            "tool_rounds_used": 0,
            "max_tool_rounds": 1,
            "final_round": False,
        },
        config={"configurable": {"thread_id": "no-tools-unit"}},
    )

    assert len(model.invocations) == 1
    assert result["final_opinion"] == "Answer without tools."


def test_repeated_tool_results_do_not_duplicate_retrieved_docs(monkeypatch):
    # Regression test: two retrieval calls returning the same chunks used to
    # append them twice, inflating the evidence block with repeated sources. A
    # live run showed 100 provider documents collapsing to only 30 distinct
    # chunks. Both calls sit in one AIMessage so the tool-round budget cannot
    # mask the duplication.
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"chunk_id": "chunk-1", "text": "shared evidence", "url": "https://e.test/1"},
            {"chunk_id": "chunk-2", "text": "other evidence", "url": "https://e.test/2"},
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "knowledge_retrieval", "args": {"query": "q1"}, "id": "c1"},
                    {"name": "knowledge_retrieval", "args": {"query": "q2"}, "id": "c2"},
                ],
            ),
            AIMessage(content="Grounded answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        graph_input(), config={"configurable": {"thread_id": "dedup-unit"}}
    )

    texts = [doc["text"] for doc in result["retrieved_docs"]]
    assert texts == ["shared evidence", "other evidence"], "the repeated chunk must appear once"


def test_distinct_same_page_snippets_are_kept(monkeypatch):
    # Dedup must not collapse genuinely different snippets that share a URL.
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "first snippet", "url": "https://e.test/same"},
            {"text": "second snippet", "url": "https://e.test/same"},
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
            ),
            AIMessage(content="Grounded answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        graph_input(), config={"configurable": {"thread_id": "dedup-snippets-unit"}}
    )

    assert [doc["text"] for doc in result["retrieved_docs"]] == [
        "first snippet",
        "second snippet",
    ]


def test_prefilled_provider_evidence_is_not_duplicated_by_retrieval(monkeypatch):
    # Provider evidence is injected before the turn runs; if retrieval returns
    # the same chunk it must not be stored a second time.
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"chunk_id": "chunk-9", "text": "provider chunk", "url": "https://e.test/9"}
        ],
    )
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
            ),
            AIMessage(content="Grounded answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model)
    result = graph.invoke(
        {
            **graph_input(),
            "retrieved_docs": [
                {"chunk_id": "chunk-9", "text": "provider chunk", "url": "https://e.test/9"}
            ],
        },
        config={"configurable": {"thread_id": "dedup-provider-unit"}},
    )

    assert len(result["retrieved_docs"]) == 1
