"""Turn-boundary tests for ``extract_opinion``.

Regression coverage: a discussion agent's thread is checkpointed for the whole
discussion, so its message list contains every previous turn. When a turn
produced no usable text the reverse scan used to walk back past the current
turn and return an *earlier* turn's opinion, which was then published as this
turn's contribution. Two occurrences were found across 60 non-initial turns of
two live runs (byte-identical output; difflib ratio 1.000).
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from qubettera.agents.utils.agent_utils import extract_opinion


def conversation(*messages):
    return {
        "final_opinion": "",
        "messages": list(messages),
    }


def test_strict_mode_does_not_return_a_previous_turns_opinion():
    """The core regression: turn 2 is empty, turn 1 must not be republished."""
    result = conversation(
        HumanMessage(content="turn 1 question"),
        AIMessage(content="TURN ONE ANSWER"),
        HumanMessage(content="turn 2 question"),
        AIMessage(content=""),
    )

    # ``since=2`` is the index of turn 2's HumanMessage, as the adapter supplies.
    assert extract_opinion(result, since=2, allow_history=False) == ""
    # The lossy fallback still finds the older text, which is why callers that
    # need a genuine this-turn answer must opt into strict mode.
    assert extract_opinion(result) == "TURN ONE ANSWER"


def test_strict_mode_returns_the_current_turns_own_answer():
    result = conversation(
        HumanMessage(content="turn 1 question"),
        AIMessage(content="TURN ONE ANSWER"),
        HumanMessage(content="turn 2 question"),
        AIMessage(content="TURN TWO ANSWER"),
    )

    assert extract_opinion(result, since=2, allow_history=False) == "TURN TWO ANSWER"


def test_strict_mode_ignores_tool_only_messages_within_the_turn():
    """A tool-call message is not an answer, so the scan must skip it."""
    result = conversation(
        HumanMessage(content="turn 1 question"),
        AIMessage(content="TURN ONE ANSWER"),
        HumanMessage(content="turn 2 question"),
        AIMessage(
            content="",
            tool_calls=[{"name": "knowledge_retrieval", "args": {"query": "q"}, "id": "c1"}],
        ),
    )

    assert extract_opinion(result, since=2, allow_history=False) == ""


def test_final_opinion_field_still_wins_under_strict_mode():
    result = {
        "final_opinion": "Dedicated field answer",
        "messages": [HumanMessage(content="q"), AIMessage(content="Dedicated field answer")],
    }

    assert extract_opinion(result, since=1, allow_history=False) == "Dedicated field answer"


def test_strict_mode_without_a_boundary_returns_nothing():
    # Strictness with no boundary cannot prove the text belongs to this turn,
    # so it must decline rather than guess.
    result = conversation(AIMessage(content="SOME OLDER ANSWER"))

    assert extract_opinion(result, allow_history=False) == ""


def test_default_behaviour_is_unchanged_for_existing_callers():
    result = conversation(AIMessage(content="Standalone answer"))

    assert extract_opinion(result) == "Standalone answer"


def test_since_beyond_the_message_list_is_tolerated():
    # A checkpoint that advanced further than the caller expected must degrade
    # to "nothing this turn", not crash.
    result = conversation(HumanMessage(content="q"), AIMessage(content="answer"))

    assert extract_opinion(result, since=99, allow_history=False) == ""
