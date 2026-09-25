from qubettera.discussion.models import DiscussionBrief, EvidenceItem, RoutedMessage, TurnRequest
from qubettera.discussion.week2_adapter import Week2AgentRuntime

import pytest

from langchain_core.messages import AIMessage


class ScriptedModel:
    def __init__(self):
        self.invocations = []
        self.responses = [AIMessage(content="initial answer"), AIMessage(content="round one answer")]

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


def make_request(round_number, incoming=(), previous=""):
    return TurnRequest(
        discussion_id="discussion-7",
        phase="initial" if round_number == 0 else "discussion",
        round_number=round_number,
        sequence_number=round_number + 1,
        agent_id="dr_aris",
        recipient_ids=("prof_elena", "grad_student"),
        brief=DiscussionBrief(
            objective="Choose a feasible option.",
            constraints=("Limited budget",),
            topics=("Option A versus option B",),
        ),
        incoming_messages=incoming,
        previous_opinion=previous,
    )


def test_adapter_uses_stable_agent_thread_and_injects_routed_context():
    model = ScriptedModel()
    runtime = Week2AgentRuntime(model=model, tools=[])
    initial = runtime.run_turn(make_request(0))
    neighbor = RoutedMessage(
        message_id="neighbor-1",
        discussion_id="discussion-7",
        phase="initial",
        round_number=0,
        sequence_number=2,
        sender_id="prof_elena",
        recipient_ids=("dr_aris",),
        content="Dense layers are easier to stabilize.",
        opinion="Prefer dense layers.",
    )
    later = runtime.run_turn(make_request(1, (neighbor,), initial.opinion_text))

    assert initial.response_text == "initial answer"
    assert later.response_text == "round one answer"
    assert initial.metadata["thread_id"] == "discussion-7:dr_aris"
    assert later.metadata["thread_id"] == "discussion-7:dr_aris"
    second_prompt = model.invocations[-1][-1].content
    assert "prof_elena: Dense layers are easier to stabilize." in second_prompt
    assert "initial answer" in second_prompt


def test_supplied_rag_evidence_does_not_trigger_duplicate_retrieval():
    model = ScriptedModel()
    model.responses = [AIMessage(content="grounded answer")]
    runtime = Week2AgentRuntime(model=model, tools=[])
    request = make_request(0)
    request = type(request)(
        **{
            **request.__dict__,
            "evidence": (
                EvidenceItem(
                    text="Measured evidence.",
                    title="Study",
                    url="https://example.test/study",
                ),
            ),
        }
    )

    result = runtime.run_turn(request)

    assert result.response_text == "grounded answer"
    assert len(model.invocations) == 1
    assert result.metadata["internal_retrieved_docs"] == 1


def test_mid_discussion_turn_keeps_a_fresh_tool_budget_across_rounds(monkeypatch):
    # Regression test: the discussion checkpoints agent state per thread, so a
    # tool round spent in round 0 used to make every later turn look exhausted.
    # The adapter must reset the budget so later rounds can still retrieve.
    from langchain_core.messages import SystemMessage

    from qubettera.agents.tools import retrieval_tool

    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/x", "title": "Study"}
        ],
    )

    def tool_call(call_id):
        return AIMessage(
            content="",
            tool_calls=[
                {"name": "knowledge_retrieval", "args": {"query": "q"}, "id": call_id}
            ],
        )

    model = ScriptedModel()
    model.responses = [
        tool_call("c1"),
        AIMessage(content="round zero answer"),
        tool_call("c2"),
        AIMessage(content="round one answer"),
    ]
    runtime = Week2AgentRuntime(model=model)

    initial = runtime.run_turn(make_request(0))
    later = runtime.run_turn(make_request(1, previous=initial.opinion_text))

    assert later.response_text == "round one answer"
    # The second turn's first model call must still offer the mandatory
    # retrieval instruction rather than the spent-budget framing.
    system_prompt = model.invocations[2][0]
    assert isinstance(system_prompt, SystemMessage)
    assert "MANDATORY" in system_prompt.content
    assert "This is not the final round." in system_prompt.content


def test_only_the_final_round_is_framed_as_the_final_synthesis(monkeypatch):
    from langchain_core.messages import SystemMessage

    from qubettera.agents.tools import retrieval_tool

    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/f", "title": "Study"}
        ],
    )
    model = ScriptedModel()
    model.responses = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}
            ],
        ),
        AIMessage(content="final answer"),
    ]
    runtime = Week2AgentRuntime(model=model)

    request = make_request(3)
    runtime.run_turn(type(request)(**{**request.__dict__, "is_final_round": True}))

    # The final round retrieves fresh evidence first, then synthesizes.
    assert "MANDATORY" in model.invocations[0][0].content
    final_prompt = model.invocations[1][0]
    assert isinstance(final_prompt, SystemMessage)
    assert "final comprehensive persona recommendation" in final_prompt.content


def test_an_empty_turn_cannot_republish_the_previous_round(monkeypatch):
    """Regression: a discussion agent's thread outlives the turn.

    The thread ID is stable for the whole discussion, so its checked message
    history still holds round 0's text when round 1 runs. An empty round 1 used
    to be resolved by a reverse history scan that walked straight back into
    round 0 and published that text as round 1's contribution — byte-identical
    output in two live runs.
    """
    from langchain_core.messages import SystemMessage

    from qubettera.agents.tools import retrieval_tool

    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/x", "title": "Study"}
        ],
    )

    def tool_call(call_id):
        return AIMessage(
            content="",
            tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": call_id}],
        )

    model = ScriptedModel()
    model.responses = [
        tool_call("c1"),
        AIMessage(content="ROUND ZERO ANSWER"),
        # Round 1 answers nothing, and neither does the retry nudge.
        AIMessage(content=""),
        AIMessage(content=""),
    ]
    runtime = Week2AgentRuntime(model=model)

    initial = runtime.run_turn(make_request(0))
    assert initial.opinion_text == "ROUND ZERO ANSWER"

    # Round 0's text is still in the checkpointed history, but it is not round
    # 1's output, so the turn must fail loudly rather than republish it.
    with pytest.raises(RuntimeError, match="returned no final response"):
        runtime.run_turn(make_request(1, previous=initial.opinion_text))


def test_an_empty_turn_recovers_via_the_retry_nudge(monkeypatch):
    """An empty response is retried once, so a transient blank is survivable."""
    from qubettera.agents.tools import retrieval_tool

    monkeypatch.setattr(
        retrieval_tool,
        "retrieve",
        lambda query, top_k, rerank: [
            {"text": "evidence", "url": "https://example.test/x", "title": "Study"}
        ],
    )

    def tool_call(call_id):
        return AIMessage(
            content="",
            tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": call_id}],
        )

    model = ScriptedModel()
    model.responses = [
        tool_call("c1"),
        AIMessage(content="ROUND ZERO ANSWER"),
        AIMessage(content=""),
        AIMessage(content="ROUND ONE RECOVERED"),
    ]
    runtime = Week2AgentRuntime(model=model)

    initial = runtime.run_turn(make_request(0))
    later = runtime.run_turn(make_request(1, previous=initial.opinion_text))

    assert later.opinion_text == "ROUND ONE RECOVERED"
    nudge = model.invocations[-1][-1]
    assert "no answer text" in nudge.content


def test_the_adapter_supplies_the_full_web_ladder_budget():
    """The ladder is opt-in via ``max_web_rounds``; the adapter is the opt-in."""
    model = ScriptedModel()
    model.responses = [AIMessage(content="answer")]
    runtime = Week2AgentRuntime(model=model, tools=[])

    runtime.run_turn(make_request(0))
    system_prompt = model.invocations[0][0]

    # With max_web_rounds supplied, the graph uses the ladder framing rather
    # than the pre-ladder "tools exhausted" wording.
    assert "MANDATORY" in system_prompt.content

