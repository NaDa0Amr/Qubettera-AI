"""Per-turn web-search budget tests.

Regression coverage: the budget used to be derived by counting message names over
the whole checkpointed ``messages`` history, which made it a lifetime-of-agent
budget. An agent that spent it in an early round was silently locked out of web
search for every later round of the discussion.
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from qubettera.agents.agent.graph import build_graph, max_web_searches_per_turn
from qubettera.agents.personas import load_persona


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


class RecordingSearch:
    """Stand-in for ``live_web_search`` that records the queries it receives."""

    def __init__(self) -> None:
        self.queries: list[str] = []

        @tool("live_web_search")
        def _search(query: str) -> str:
            """Search the web."""
            self.queries.append(query)
            return f"No results found for query: {query}"

        self.search = _search


def web_search_call(call_id: str, query: str = "q"):
    return AIMessage(
        content="",
        tool_calls=[{"name": "live_web_search", "args": {"query": query}, "id": call_id}],
    )


def turn_input(prompt: str, **overrides):
    """Mirror what the discussion adapter supplies on every turn."""
    return {
        "messages": [HumanMessage(content=prompt)],
        "persona": load_persona("moe_efficiency"),
        "retrieved_docs": [],
        "retrieval_queries": [],
        "tool_rounds_used": 0,
        "max_tool_rounds": 1,
        "kb_rounds_used": 0,
        "web_rounds_used": 0,
        "max_web_rounds": 1,
        "kb_insufficient": False,
        "web_searches_used": 0,
        "max_web_searches": 5,
        "final_round": True,
        **overrides,
    }


def test_web_search_budget_is_not_spent_by_prior_turns():
    """An exhausted budget in turn 1 must not block web search in turn 2."""
    search = RecordingSearch()
    model = ScriptedModel(
        [
            web_search_call("c1", "first"),
            AIMessage(content="First turn answer."),
            web_search_call("c2", "second"),
            AIMessage(content="Second turn answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model, tools=[search.search])
    config = {"configurable": {"thread_id": "web-budget-reset"}}

    first = graph.invoke(turn_input("first question", max_web_searches=1), config=config)
    assert first["web_searches_used"] == 1
    assert search.queries == ["first"]

    # Turn 2: the adapter resets the counter, so a fresh budget applies.
    second = graph.invoke(turn_input("second question", max_web_searches=1), config=config)

    assert second["web_searches_used"] == 1
    assert search.queries == ["first", "second"], "the second turn must regain a fresh budget"


def test_web_search_budget_blocks_once_exhausted_within_a_turn():
    """Within one turn the search cap still applies and the skip is reported.

    Both searches are issued in a single tool round on purpose: two separate
    rounds would hit the web-*round* budget first, so the round limit would be
    under test instead of the search limit this case is about.
    """
    search = RecordingSearch()
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "live_web_search", "args": {"query": "first"}, "id": "c1"},
                    {"name": "live_web_search", "args": {"query": "second"}, "id": "c2"},
                ],
            ),
            AIMessage(content="Answer."),
        ]
    )
    graph = build_graph(checkpointer=InMemorySaver(), model=model, tools=[search.search])

    result = graph.invoke(
        turn_input("question", max_web_searches=1),
        config={"configurable": {"thread_id": "web-budget-cap"}},
    )

    assert result["web_searches_used"] == 1
    assert search.queries == ["first"], "the second search must be skipped once the cap is hit"
    limited = [m for m in result["messages"] if "Web search limit reached" in str(m.content)]
    assert limited, "the skipped call must report the limit to the agent"
    assert "per turn" in str(limited[0].content)


def test_max_web_searches_per_turn_validates_env(monkeypatch):
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "3")
    assert max_web_searches_per_turn() == 3
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "0")
    assert max_web_searches_per_turn() == 0
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "not-a-number")
    with pytest.raises(RuntimeError, match="must be an integer"):
        max_web_searches_per_turn()
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "-1")
    with pytest.raises(RuntimeError, match="zero or greater"):
        max_web_searches_per_turn()


def test_max_web_searches_per_turn_defaults_to_five(monkeypatch):
    monkeypatch.delenv("MAX_WEB_SEARCHES_PER_RUN", raising=False)
    assert max_web_searches_per_turn() == 5
