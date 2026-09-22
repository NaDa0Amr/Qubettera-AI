from qubettera.discussion.models import DiscussionBrief, EvidenceItem, RoutedMessage, TurnRequest
from qubettera.discussion.week2_adapter import Week2AgentRuntime

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
