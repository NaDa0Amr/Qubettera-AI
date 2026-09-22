from qubettera.discussion.agent_graph import AgentGraph
from qubettera.discussion.config import load_discussion_config
from qubettera.discussion.fakes import DeterministicAgentRuntime, DeterministicRetrievalProvider
from qubettera.discussion.orchestrator import DiscussionOrchestrator
from qubettera.discussion.run_log import JsonlEventSink


def test_five_agents_three_rounds_yields_at_least_fifteen_discussion_retrieval_calls(tmp_path):
    graph = AgentGraph.from_json("resources/configs/agent_graph.json")
    config = load_discussion_config("resources/configs/discussion.json")
    runtime = DeterministicAgentRuntime()
    retrieval_provider = DeterministicRetrievalProvider()
    orchestrator = DiscussionOrchestrator(
        graph=graph,
        agent_runtime=runtime,
        retrieval_provider=retrieval_provider,
        event_sink=JsonlEventSink(tmp_path / "log.jsonl"),
        id_factory=lambda: "known-discussion",
        clock=lambda: "2026-09-07T00:00:00+00:00",
    )

    result = orchestrator.run(config)

    discussion_calls = [
        request for _, request in retrieval_provider.retrieve_calls if request.phase == "discussion"
    ]
    assert len(config.participant_ids) == 5
    assert config.num_rounds == 3
    assert len(discussion_calls) == 15

    for round_number in (1, 2, 3):
        assert sum(request.round_number == round_number for request in discussion_calls) == 5

    # Every discussion-round call produced a nonblank query.
    assert all(query.strip() for query, request in retrieval_provider.retrieve_calls if request.phase == "discussion")

    # The retrieved evidence actually reaches the message (and therefore would
    # reach the LLM prompt via week3.context.render_turn_prompt).
    discussion_messages = [m for m in result.messages if m.phase == "discussion"]
    assert all(message.evidence for message in discussion_messages)
    assert all(message.retrieval_query for message in discussion_messages)


def test_round_two_query_reflects_round_one_messages_not_only_the_original_topic(tmp_path):
    graph = AgentGraph.from_json("resources/configs/agent_graph.json")
    config = load_discussion_config("resources/configs/discussion.json")
    runtime = DeterministicAgentRuntime()
    retrieval_provider = DeterministicRetrievalProvider()
    orchestrator = DiscussionOrchestrator(
        graph=graph,
        agent_runtime=runtime,
        retrieval_provider=retrieval_provider,
        event_sink=JsonlEventSink(tmp_path / "log.jsonl"),
        id_factory=lambda: "known-discussion",
        clock=lambda: "2026-09-07T00:00:00+00:00",
    )
    orchestrator.run(config)

    round_two_query = next(
        query
        for query, request in retrieval_provider.retrieve_calls
        if request.phase == "discussion" and request.round_number == 2 and request.agent_id == "dr_aris"
    )

    # dr_aris's round-1 neighbors are prof_elena and grad_student per the
    # configured graph; their round-1 output must show up in the round-2 query.
    assert "prof_elena" in round_two_query
    assert "grad_student" in round_two_query
