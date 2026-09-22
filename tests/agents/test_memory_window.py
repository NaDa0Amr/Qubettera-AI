from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from qubettera.agents.agent.graph import trim_start


def test_trim_start_keeps_five_human_exchanges_and_associated_messages():
    messages = []
    for index in range(7):
        messages.extend(
            [
                HumanMessage(content=f"question {index}"),
                AIMessage(content=f"answer {index}"),
            ]
        )
    cutoff = trim_start(messages, exchanges=5)
    assert messages[cutoff].content == "question 2"
    assert sum(isinstance(message, HumanMessage) for message in messages[cutoff:]) == 5


def test_trim_window_keeps_tool_result_after_retained_human_turn():
    messages = [
        HumanMessage(content="old"),
        AIMessage(content="old answer"),
        HumanMessage(content="recent"),
        AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
        ToolMessage(content="evidence", tool_call_id="1"),
        AIMessage(content="recent answer"),
    ]
    cutoff = trim_start(messages, exchanges=1)
    assert messages[cutoff].content == "recent"
    assert any(isinstance(message, ToolMessage) for message in messages[cutoff:])

