import json

import pytest

from week3.agent_graph import AgentGraph, GraphConfigurationError
from week3.config import load_discussion_config
from week3.fakes import DeterministicAgentRuntime
from week3.orchestrator import DiscussionExecutionError, DiscussionOrchestrator
from week3.run_log import JsonlEventSink


def build_orchestrator(tmp_path, runtime=None):
    graph = AgentGraph.from_json("configs/agent_graph.json")
    runtime = runtime or DeterministicAgentRuntime()
    log_path = tmp_path / "known-discussion.jsonl"
    orchestrator = DiscussionOrchestrator(
        graph=graph,
        agent_runtime=runtime,
        event_sink=JsonlEventSink(log_path),
        id_factory=lambda: "known-discussion",
        clock=lambda: "2026-09-07T00:00:00+00:00",
    )
    return orchestrator, runtime, log_path


def test_three_round_run_logs_one_output_per_agent_per_round(tmp_path):
    config = load_discussion_config("configs/discussion.json")
    orchestrator, runtime, log_path = build_orchestrator(tmp_path)

    result = orchestrator.run(config)
    discussion_messages = [m for m in result.messages if m.phase == "discussion"]
    initial_messages = [m for m in result.messages if m.phase == "initial"]
    log_events = [json.loads(line) for line in log_path.read_text().splitlines()]

    assert result.status == "completed"
    assert len(initial_messages) == 5
    assert len(discussion_messages) == 15
    assert len(runtime.requests) == 20
    for round_number in (1, 2, 3):
        assert sum(m.round_number == round_number for m in discussion_messages) == 5
    assert sum(event["event"] == "turn_completed" for event in log_events) == 20
    assert log_events[0]["event"] == "discussion_started"
    assert log_events[-1]["event"] == "discussion_completed"


def test_next_round_uses_only_routed_previous_snapshot(tmp_path):
    config = load_discussion_config("configs/discussion.json")
    orchestrator, runtime, _ = build_orchestrator(tmp_path)
    orchestrator.run(config)

    round_one_aris = next(
        request
        for request in runtime.requests
        if request.phase == "discussion"
        and request.round_number == 1
        and request.agent_id == "dr_aris"
    )
    assert [message.sender_id for message in round_one_aris.incoming_messages] == [
        "prof_elena",
        "grad_student",
    ]
    assert all(message.phase == "initial" for message in round_one_aris.incoming_messages)

    round_two_aris = next(
        request
        for request in runtime.requests
        if request.phase == "discussion"
        and request.round_number == 2
        and request.agent_id == "dr_aris"
    )
    assert [message.sender_id for message in round_two_aris.incoming_messages] == [
        "prof_elena",
        "grad_student",
    ]
    assert all(message.round_number == 1 for message in round_two_aris.incoming_messages)


def test_participants_must_match_graph_nodes(tmp_path):
    config = load_discussion_config("configs/discussion.json")
    bad_config = type(config)(
        brief=config.brief,
        participant_ids=config.participant_ids[:-1],
        num_rounds=3,
    )
    orchestrator, _, _ = build_orchestrator(tmp_path)

    with pytest.raises(GraphConfigurationError, match="must match the graph nodes exactly"):
        orchestrator.run(bad_config)


class FailingRuntime(DeterministicAgentRuntime):
    def run_turn(self, request):
        if request.sequence_number == 3:
            raise RuntimeError("planned agent failure")
        return super().run_turn(request)


def test_failure_is_reported_with_completed_partial_history(tmp_path):
    config = load_discussion_config("configs/discussion.json")
    orchestrator, _, log_path = build_orchestrator(tmp_path, FailingRuntime())

    with pytest.raises(DiscussionExecutionError) as captured:
        orchestrator.run(config)

    assert captured.value.partial_result.status == "failed"
    assert len(captured.value.partial_result.messages) == 2
    events = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert events[-1]["event"] == "discussion_failed"
    assert events[-1]["completed_message_count"] == 2
