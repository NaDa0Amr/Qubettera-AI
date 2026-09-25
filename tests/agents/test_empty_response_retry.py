"""Empty-response handling in ``call_model``.

Regression coverage: a model can return an ``AIMessage`` with no tool calls and
no text. That used to end the turn with ``final_opinion == ""``, which the
caller's history scan then resolved to a *previous turn's* opinion — publishing
stale text as the current contribution. Before handing back an empty opinion,
``call_model`` now gives the model one explicit chance to answer directly.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from qubettera.agents.agent.graph import build_graph
from qubettera.agents.personas import load_persona


class ScriptedModel:
    """One instance serves both the tool-bound and the plain retry call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


def agent_input(**overrides):
    return {
        "messages": [HumanMessage(content="Which index should we use?")],
        "persona": load_persona("moe_efficiency"),
        "task": "Pick an index.",
        "retrieved_docs": [],
        "retrieval_queries": [],
        **overrides,
    }


def run(model, **overrides):
    # No tools: this isolates the direct-answer retry from the mandatory
    # retrieval nudge, which only applies to a tool-bound graph.
    graph = build_graph(checkpointer=InMemorySaver(), model=model, tools=[])
    return graph.invoke(
        agent_input(**overrides),
        config={"configurable": {"thread_id": f"retry-{len(model.responses)}-{len(overrides)}"}},
    )


def test_empty_response_is_retried_and_recovers_a_real_answer():
    model = ScriptedModel([AIMessage(content=""), AIMessage(content="Use a B-tree index.")])

    result = run(model)

    assert result["final_opinion"] == "Use a B-tree index."
    assert len(model.invocations) == 2, "exactly one retry"
    nudge = model.invocations[1][-1]
    assert isinstance(nudge, HumanMessage)
    assert "no answer text" in nudge.content
    assert "Do NOT call any tools" in nudge.content


def test_whitespace_only_response_is_treated_as_empty():
    model = ScriptedModel([AIMessage(content="   \n  "), AIMessage(content="Recovered.")])

    result = run(model)

    assert result["final_opinion"] == "Recovered."
    assert len(model.invocations) == 2


def test_a_still_empty_retry_yields_an_empty_opinion_and_retries_only_once():
    model = ScriptedModel([AIMessage(content=""), AIMessage(content="")])

    result = run(model)

    assert result["final_opinion"] == "", "the caller must see a genuinely empty turn"
    assert len(model.invocations) == 2, "must not loop; the turn is left for the caller to fail"


def test_a_non_empty_response_is_not_retried():
    model = ScriptedModel([AIMessage(content="Use a B-tree index.")])

    result = run(model)

    assert result["final_opinion"] == "Use a B-tree index."
    assert len(model.invocations) == 1


def test_a_tool_call_response_is_not_retried():
    """A tool call is a valid step, not an empty answer."""
    model = ScriptedModel(
        [
            AIMessage(content="", tool_calls=[{"name": "nope", "args": {}, "id": "c1"}]),
            AIMessage(content="Final answer."),
        ]
    )

    result = run(model)

    # The unknown tool is reported back to the model, which then answers.
    assert result["final_opinion"] == "Final answer."
    assert len(model.invocations) == 2


def test_a_failing_retry_does_not_crash_the_turn():
    class Exploding(ScriptedModel):
        def invoke(self, messages):
            self.invocations.append(messages)
            if len(self.invocations) > 1:
                raise RuntimeError("upstream unavailable")
            return self.responses.pop(0)

    model = Exploding([AIMessage(content="")])

    result = run(model)

    assert result["final_opinion"] == "", "a failed retry must degrade, not raise"


def test_the_retry_does_not_reuse_a_previous_turns_text():
    """The whole point: no stale harvest when the current turn stays empty."""
    model = ScriptedModel([AIMessage(content="")])
    graph = build_graph(checkpointer=InMemorySaver(), model=model, tools=[])
    config = {"configurable": {"thread_id": "retry-stale"}}

    # Turn 1 produces a real answer.
    model.responses = [AIMessage(content="TURN ONE ANSWER")]
    first = graph.invoke(agent_input(), config=config)
    assert first["final_opinion"] == "TURN ONE ANSWER"

    # Turn 2 stays empty even after the retry. The checkpointed history still
    # holds turn 1's text, so it must not leak into this state's opinion.
    model.responses = [AIMessage(content=""), AIMessage(content="")]
    second = graph.invoke(agent_input(), config=config)

    assert second["final_opinion"] == ""
    assert second["final_opinion"] != first["final_opinion"]
