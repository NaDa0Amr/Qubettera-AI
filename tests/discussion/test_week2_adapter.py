from uuid import UUID

from qubettera.discussion.models import DiscussionBrief, EvidenceItem, RoutedMessage, TurnRequest
from qubettera.discussion.week2_adapter import Week2AgentRuntime

from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk


class ScriptedModel:
    def __init__(self):
        self.invocations = []
        self.responses = [AIMessage(content="initial answer. No supporting evidence is available."), AIMessage(content="round one answer. No supporting evidence is available.")]

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.responses.pop(0)


class StreamingModel(SimpleChatModel):
    @property
    def _llm_type(self):
        return "test-streaming-model"

    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        raise AssertionError("The discussion runtime must request the streaming transport")

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for text in ("streamed ", "answer. No supporting evidence is available."):
            yield ChatGenerationChunk(message=AIMessageChunk(content=text))


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

    assert initial.response_text == "initial answer. No supporting evidence is available."
    assert later.response_text == "round one answer. No supporting evidence is available."
    assert initial.metadata["thread_id"] == "discussion-7:dr_aris"
    assert later.metadata["thread_id"] == "discussion-7:dr_aris"
    second_prompt = next(m.content for m in reversed(model.invocations[-1]) if m.type == "human")
    assert "prof_elena: Dense layers are easier to stabilize." in second_prompt
    assert "initial answer" in second_prompt


def test_supplied_rag_evidence_does_not_trigger_duplicate_retrieval():
    model = ScriptedModel()
    model.responses = [AIMessage(content="grounded answer [Source: https://example.test/study]")]
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

    assert result.response_text == "grounded answer [Source: https://example.test/study]"
    assert len(model.invocations) == 1
    assert result.metadata["internal_retrieved_docs"] == 1


def test_adapter_labels_streamed_tokens_with_the_current_turn():
    events = []
    runtime = Week2AgentRuntime(model=ScriptedModel(), tools=[], token_sink=events.append)

    class StreamingGraph:
        def invoke(self, graph_input, config):
            assert config["configurable"]["stream_tokens"] is True
            callback = config["callbacks"][0]
            callback.on_llm_new_token(
                "partial ",
                run_id=UUID("00000000-0000-0000-0000-000000000123"),
            )
            return {
                **graph_input,
                "messages": [AIMessage(content="final. No supporting evidence is available.", id="answer")],
                "final_opinion": "final. No supporting evidence is available.",
            }

        def update_state(self, config, values, as_node):
            return None

    runtime.graph = StreamingGraph()
    runtime.run_turn(make_request(1))

    assert events == [
        {
            "event": "token_chunk",
            "discussion_id": "discussion-7",
            "agent_id": "dr_aris",
            "round": 1,
            "token": "partial ",
            "run_id": "00000000-0000-0000-0000-000000000123",
        }
    ]


def test_runtime_uses_model_streaming_transport_when_sink_is_present():
    events = []
    with Week2AgentRuntime(model=StreamingModel(), tools=[], token_sink=events.append) as runtime:
        result = runtime.run_turn(make_request(0))

    assert result.response_text == "streamed answer. No supporting evidence is available."
    assert "".join(event["token"] for event in events) == result.response_text
    assert {event["agent_id"] for event in events} == {"dr_aris"}
    assert {event["round"] for event in events} == {0}
