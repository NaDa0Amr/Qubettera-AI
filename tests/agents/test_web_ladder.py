"""KB-first ladder tests.

Regression coverage: ``MAX_TOOL_ROUNDS`` used to gate *every* tool on one
counter, so the moment an agent called ``knowledge_retrieval`` its only tool
round was spent, the graph routed to END, and ``synthesis_mode`` told the model
"Do NOT call any tools in this turn." The documented "if the KB is insufficient,
search the web" fallback was therefore structurally unreachable — proven by a
live A/B where ``MAX_TOOL_ROUNDS=1`` produced 3 KB calls and **zero** web
searches, while ``MAX_TOOL_ROUNDS=3`` produced 3 KB calls then 4 web searches.

The ladder gives web search its own round budget (``MAX_WEB_ROUNDS``) and opens
it once the knowledge base has been consulted or has proved insufficient.

Graphs here bind a real ``knowledge_retrieval`` (with ``retrieve`` patched) plus
an injected web tool. Binding only the web tool would make every KB call resolve
to "Unknown tool", which removes the KB-first ordering entirely and would let
these tests pass for the wrong reason.
"""
from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from qubettera.agents.agent.graph import build_graph, max_web_rounds_per_turn
from qubettera.agents.personas import load_persona
from qubettera.agents.tools import retrieval_tool


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


class RecordingWeb:
    """A real ``@tool`` that records queries and returns prose.

    ``graph.py`` binds ``live_web_search`` into ``_DEFAULT_TOOLS`` at import
    time, so monkeypatching ``search_tool`` would not affect the compiled graph;
    the stand-in must be injected through ``build_graph(tools=...)``.
    """

    def __init__(self) -> None:
        self.queries: list[str] = []

        @tool("live_web_search")
        def _search(query: str) -> str:
            """Search the web for current information."""
            self.queries.append(query)
            return f"Web result for {query}"

        self.search = _search


def kb_call(call_id: str, query: str = "kb query") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "knowledge_retrieval", "args": {"query": query}, "id": call_id}],
    )


def web_call(call_id: str, query: str = "web query") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "live_web_search", "args": {"query": query}, "id": call_id}],
    )


def turn_input(prompt: str = "question", **overrides):
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


def patch_kb(monkeypatch, similarity: float, text: str = "kb evidence"):
    """Patch the KB backend so ``knowledge_retrieval`` reports a given quality."""
    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": text, "url": "https://example.test/kb", "title": "KB", "similarity": similarity}
        ],
    )
    # Keep the weak-KB path hermetic: no LLM query regeneration, no second call.
    monkeypatch.setattr(retrieval_tool, "_regenerate_query_with_llm", lambda *a, **k: None)


@pytest.fixture
def strong_kb(monkeypatch):
    patch_kb(monkeypatch, similarity=0.8)


@pytest.fixture
def weak_kb(monkeypatch):
    patch_kb(monkeypatch, similarity=0.2, text="weak match")


def build(web: RecordingWeb, model: ScriptedModel, *, with_kb: bool = True):
    tools = [web.search] if not with_kb else [retrieval_tool.knowledge_retrieval, web.search]
    return build_graph(checkpointer=InMemorySaver(), model=model, tools=tools)


def run(graph, **overrides):
    return graph.invoke(
        turn_input(**overrides),
        config={"configurable": {"thread_id": f"ladder-{id(graph)}-{len(overrides)}"}},
    )


def test_web_search_runs_after_the_kb_round_is_spent(strong_kb):
    """The core regression: a spent KB round must not close the web path.

    With ``max_tool_rounds=1`` the KB call consumes the only tool round, so this
    is exactly the configuration in which the web fallback used to be dead.
    """
    web = RecordingWeb()
    model = ScriptedModel([kb_call("c1"), web_call("c2", "external"), AIMessage(content="Answer.")])
    graph = build(web, model)

    result = run(graph)

    assert web.queries == ["external"], "the web tool must actually be invoked"
    assert result["kb_rounds_used"] == 1
    assert result["web_rounds_used"] == 1
    assert result["web_searches_used"] == 1
    assert result["retrieval_queries"] == ["kb query"]


def test_the_two_budgets_are_independent(strong_kb):
    """A KB round must not consume the web round (the original defect)."""
    web = RecordingWeb()
    model = ScriptedModel(
        [kb_call("c1"), web_call("c2"), web_call("c3", "second"), AIMessage(content="Answer.")]
    )
    graph = build(web, model)

    result = run(graph, max_web_rounds=2)

    assert result["kb_rounds_used"] == 1
    assert result["web_rounds_used"] == 2, "the web gets its own rounds, not the KB's leftovers"


def test_kb_first_blocks_a_web_call_made_before_any_retrieval(strong_kb):
    web = RecordingWeb()
    model = ScriptedModel([web_call("c1"), AIMessage(content="Answer.")])
    graph = build(web, model)

    result = run(graph)

    assert web.queries == [], "the web must not be used before the knowledge base"
    blocked = [m for m in result["messages"] if "Knowledge-base first" in str(m.content)]
    assert blocked, "the agent must be told why the call was skipped"


def test_weak_kb_opens_the_web_after_the_kb_round(weak_kb):
    """A KB round that could not ground the question permits the web fallback."""
    web = RecordingWeb()
    model = ScriptedModel([kb_call("c0"), web_call("c1", "fallback"), AIMessage(content="Answer.")])
    graph = build(web, model)

    result = run(graph)

    assert result["kb_insufficient"] is True
    assert web.queries == ["fallback"]


def test_web_round_budget_is_enforced(strong_kb):
    web = RecordingWeb()
    model = ScriptedModel(
        [kb_call("c1"), web_call("c2", "first"), web_call("c3", "second"), AIMessage(content="Answer.")]
    )
    graph = build(web, model)

    result = run(graph, max_web_rounds=1)

    assert web.queries == ["first"], "only one web round is allowed"
    assert result["web_rounds_used"] == 1


def test_parallel_web_calls_in_one_round_share_a_round(strong_kb):
    """Two searches issued together are one round, so a cap of 1 allows both."""
    web = RecordingWeb()
    both = AIMessage(
        content="",
        tool_calls=[
            {"name": "live_web_search", "args": {"query": "a"}, "id": "c2"},
            {"name": "live_web_search", "args": {"query": "b"}, "id": "c3"},
        ],
    )
    model = ScriptedModel([kb_call("c1"), both, AIMessage(content="Answer.")])
    graph = build(web, model)

    result = run(graph, max_web_rounds=1)

    assert web.queries == ["a", "b"]
    assert result["web_rounds_used"] == 1
    assert result["web_searches_used"] == 2


def test_synthesis_mode_stays_off_while_the_web_remains_available(strong_kb):
    """The prompt must invite the web fallback once the KB round is spent."""
    web = RecordingWeb()
    model = ScriptedModel([kb_call("c1"), web_call("c2"), AIMessage(content="Answer.")])
    graph = build(web, model)

    run(graph)

    # model.invocations[1] is the second call_model pass: the KB round is spent
    # but the web is still open, so the prompt must point at the web rather than
    # announce that evidence gathering is over.
    second_prompt = model.invocations[1][0]
    assert isinstance(second_prompt, SystemMessage)
    assert "Do NOT call any tools in this turn" not in second_prompt.content
    assert "live_web_search" in second_prompt.content
    assert "not sufficient on their own" in second_prompt.content


def test_synthesis_mode_applies_once_no_tool_is_reachable(strong_kb):
    web = RecordingWeb()
    model = ScriptedModel([kb_call("c1"), web_call("c2"), AIMessage(content="Answer.")])
    graph = build(web, model)

    run(graph, max_web_rounds=1, final_round=False)

    final_prompt = model.invocations[-1][0]
    assert "Do NOT call any tools in this turn" in final_prompt.content


def test_web_only_graph_is_not_blocked_by_kb_first(strong_kb):
    """With no KB tool bound there is nothing to consult first."""
    web = RecordingWeb()
    model = ScriptedModel([web_call("c1", "direct"), AIMessage(content="Answer.")])
    graph = build(web, model, with_kb=False)

    result = run(graph)

    assert web.queries == ["direct"]
    assert result["web_searches_used"] == 1


def test_stale_checkpoint_counters_cannot_make_a_reset_turn_look_spent(strong_kb):
    """A caller that resets ``tool_rounds_used`` must regain both budgets.

    ``kb_rounds_used``/``web_rounds_used`` are checkpointed like every other
    state field, so they must be clamped to ``tool_rounds_used``; otherwise a
    reset turn would look exhausted — the same sticky-state trap that previously
    bit ``synthesis_mode`` and ``web_searches_used``.
    """
    web = RecordingWeb()
    model = ScriptedModel([kb_call("c1", "first kb"), AIMessage(content="First.")])
    graph = build(web, model)
    config = {"configurable": {"thread_id": "ladder-reset"}}
    graph.invoke(turn_input(), config=config)

    # Second turn: the adapter resets the counters, but the checkpoint still
    # holds the previous turn's kb/web counts.
    model.responses = [kb_call("c2", "second kb"), AIMessage(content="Second.")]
    result = graph.invoke(
        turn_input("second question", tool_rounds_used=0, kb_rounds_used=0, web_rounds_used=0),
        config=config,
    )

    assert result["kb_rounds_used"] == 1, "the reset turn must retrieve again"
    assert result["retrieval_queries"] == ["second kb"]


def test_kb_insufficient_does_not_leak_into_a_later_turn(weak_kb):
    """The ladder flag is per turn; a clean turn must not inherit it."""
    web = RecordingWeb()
    model = ScriptedModel([kb_call("c1"), AIMessage(content="First.")])
    graph = build(web, model)
    config = {"configurable": {"thread_id": "ladder-leak"}}
    first = graph.invoke(turn_input(), config=config)
    assert first["kb_insufficient"] is True

    model.responses = [AIMessage(content="Second.")]
    second = graph.invoke(turn_input("second question", kb_insufficient=False), config=config)

    assert second["kb_insufficient"] is False


def test_max_web_rounds_per_turn_defaults_to_one(monkeypatch):
    monkeypatch.delenv("MAX_WEB_ROUNDS", raising=False)
    assert max_web_rounds_per_turn() == 1


def test_max_web_rounds_per_turn_validates_env(monkeypatch):
    monkeypatch.setenv("MAX_WEB_ROUNDS", "2")
    assert max_web_rounds_per_turn() == 2
    monkeypatch.setenv("MAX_WEB_ROUNDS", "0")
    assert max_web_rounds_per_turn() == 0
    monkeypatch.setenv("MAX_WEB_ROUNDS", "not-a-number")
    with pytest.raises(RuntimeError, match="must be an integer"):
        max_web_rounds_per_turn()
    monkeypatch.setenv("MAX_WEB_ROUNDS", "-1")
    with pytest.raises(RuntimeError, match="zero or greater"):
        max_web_rounds_per_turn()


def test_kb_envelope_reports_quality(monkeypatch):
    """The graph reads KB quality from the envelope, so it must be present."""
    patch_kb(monkeypatch, similarity=0.9, text="good")
    strong = json.loads(retrieval_tool.knowledge_retrieval.invoke({"query": "q", "top_k": 1}))
    assert strong["insufficient"] is False
    assert strong["top_similarity"] == pytest.approx(0.9)

    patch_kb(monkeypatch, similarity=0.2, text="weak")
    weak = json.loads(retrieval_tool.knowledge_retrieval.invoke({"query": "q", "top_k": 1}))
    assert weak["insufficient"] is True
    assert weak["top_similarity"] == pytest.approx(0.2)


def test_unreachable_kb_permits_the_web_fallback(monkeypatch):
    """A KB that raised cannot ground a claim, so the web must stay open."""

    def boom(query, top_k, rerank):
        raise RuntimeError("knowledge base unreachable")

    monkeypatch.setattr(retrieval_tool, "retrieve", boom)
    envelope = json.loads(retrieval_tool.knowledge_retrieval.invoke({"query": "q", "top_k": 1}))
    assert envelope["insufficient"] is True
    assert envelope["top_similarity"] is None


def test_reranking_stays_disabled_on_both_kb_tools():
    """The live A/B rejected reranking; the default must not silently flip."""
    assert retrieval_tool.knowledge_retrieval.args["rerank"]["default"] is False
    assert retrieval_tool.retrieve_knowledge_base.args["rerank"]["default"] is False
