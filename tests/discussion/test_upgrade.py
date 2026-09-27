from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
import threading

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from qubettera.agents.agent.budget import InputBudget, clip
from qubettera.discussion.citations import citation_errors
from qubettera.discussion.models import EvidenceItem
from qubettera.discussion.retrieval_provider import TeamRetrievalProvider
from qubettera.discussion.week2_adapter import Week2AgentRuntime
from test_week2_adapter import make_request, ScriptedModel


URL = "https://example.test/current"
EVIDENCE = (EvidenceItem(text="Measured support", url=URL),)


def test_concurrent_cache_shares_inflight_and_clears_between_runs():
    started, release = threading.Event(), threading.Event()

    class Service:
        calls = 0

        def retrieve(self, query, top_k):
            self.calls += 1
            started.set()
            assert release.wait(5)
            return []

    service = Service()
    provider = TeamRetrievalProvider(retrieval_service=service)
    provider.begin_run()
    with ThreadPoolExecutor(max_workers=4) as executor:
        first = executor.submit(provider.retrieve, " same  QUERY ", make_request(0))
        assert started.wait(5)
        others = [executor.submit(provider.retrieve, "same query", make_request(0)) for _ in range(3)]
        release.set()
        assert first.result() == ()
        assert all(f.result() == () for f in others)
    assert service.calls == 1
    provider.top_k = 2
    provider.retrieve("same query", make_request(0))
    assert service.calls == 2
    provider.end_run()
    provider.begin_run()
    provider.retrieve("same query", make_request(0))
    assert service.calls == 3


def test_failed_retrieval_is_not_cached_and_scores_keep_their_meaning():
    class Service:
        calls = 0

        def retrieve(self, query, top_k):
            self.calls += 1
            if self.calls == 1:
                raise OSError("offline")
            return [{"text": "result", "url": URL, "distance": .8, "rrf_score": .03}]

    service = Service()
    provider = TeamRetrievalProvider(retrieval_service=service)
    assert provider.retrieve("query", make_request(0)) == ()
    assert provider.take_warnings()
    evidence = provider.retrieve("query", make_request(0))
    assert evidence[0].score is None
    assert evidence[0].metadata == {"distance": .8, "rrf_score": .03}
    assert not provider.take_warnings()


def test_query_reserves_focus_and_current_claim_with_long_brief():
    from test_retrieval_provider import make_neighbor_message
    request = make_request(1, (make_neighbor_message("prof_elena", "Current neighbor claim " * 100),), "Previous claim " * 500)
    request = replace(request, brief=replace(request.brief, objective="Objective " * 1000))
    query = TeamRetrievalProvider().build_query(request)
    assert len(query) <= 512
    assert "prof_elena" in query and "Previous claim" in query
    assert "Objective" in query


def test_citation_repair_replaces_checkpoint_draft_and_stale_evidence():
    model = ScriptedModel()
    valid = f"Repaired [Source: {URL}]"
    model.responses = [AIMessage(content="Bad [Source: https://invented.test]"), AIMessage(content=valid),
                       AIMessage(content=valid), AIMessage(content="No supporting evidence is available.")]
    with Week2AgentRuntime(model=model, tools=[]) as runtime:
        first = runtime.run_turn(replace(make_request(0), evidence=EVIDENCE))
        assert first.response_text == valid
        config = {"configurable": {"thread_id": "discussion-7:dr_aris"}}
        saved = runtime.graph.get_state(config).values
        assert saved["messages"][-1].content == valid
        assert "invented.test" not in str(saved["messages"])
        second = runtime.run_turn(make_request(1, previous=valid))
        assert second.evidence == ()
        assert second.response_text == "No supporting evidence is available."
        assert runtime.graph.get_state(config).values["final_opinion"] == second.response_text
    assert len(model.invocations) == 4


def test_unresolved_citations_are_retained_flagged_and_checkpointed():
    model = ScriptedModel()
    model.responses = [AIMessage(content="bad [Source: https://unknown.test]")] * 2
    with Week2AgentRuntime(model=model, tools=[]) as runtime:
        result = runtime.run_turn(replace(make_request(0), evidence=EVIDENCE))
        assert "https://unknown.test" in result.response_text
        assert "Validation warning" in result.response_text
        assert result.metadata["warnings"]
        saved = runtime.graph.get_state({"configurable": {"thread_id": "discussion-7:dr_aris"}}).values
        assert saved["final_opinion"] == result.response_text == saved["messages"][-1].content
    assert len(model.invocations) == 2


def test_tool_limits_reset_and_internal_tools_are_filtered(monkeypatch):
    monkeypatch.setenv("MAX_TOOL_ROUNDS", "1")
    calls = []

    @tool
    def live_web_search(query: str) -> str:
        """Search external evidence."""
        calls.append(query)
        return json.dumps({"documents": [{"text": "External support", "url": URL}]})

    @tool
    def knowledge_retrieval(query: str) -> str:
        """Forbidden internal retrieval."""
        pytest.fail("discussion used internal tool")

    model = ScriptedModel()
    model.responses = []
    for index in range(2):
        model.responses.extend([AIMessage(content="", tool_calls=[{
            "name": "live_web_search", "args": {"query": str(index)}, "id": str(index)}]),
            AIMessage(content=f"Supported [Source: {URL}]")])
    with Week2AgentRuntime(model=model, tools=[live_web_search, knowledge_retrieval]) as runtime:
        runtime.run_turn(make_request(0))
        runtime.run_turn(make_request(1))
    assert calls == ["0", "1"]


def test_all_calls_bounded_including_failed_summary_repair_and_synthesis(monkeypatch):
    monkeypatch.setenv("MODEL_CONTEXT_TOKENS", "6000")
    monkeypatch.setenv("MODEL_ANSWER_TOKENS", "1000")

    class Model(ScriptedModel):
        def invoke(self, messages):
            self.invocations.append(messages)
            assert InputBudget().size(messages) <= InputBudget().limit
            if "compact conversation memory" in str(messages):
                raise RuntimeError("summary unavailable")
            return AIMessage(content="Uncited recommendation " * 500)

    model = Model()
    with Week2AgentRuntime(model=model, tools=[]) as runtime:
        for index in range(7):
            request = replace(make_request(index, previous="old claim " * 5000),
                evidence=tuple(EvidenceItem(text="long excerpt " * 1000, url=URL + str(i)) for i in range(8)))
            result = runtime.run_turn(request)
            assert len(result.response_text) <= 6000
            assert len(result.evidence) <= 5
            assert all(len(item.text) <= 1200 for item in result.evidence)
        runtime.run_turn(replace(make_request(3), phase="synthesis", agent_id="moderator", evidence=EVIDENCE))
    assert any("compact conversation memory" in str(m) for m in model.invocations)


def test_budget_counts_tools_and_preserves_atomic_urls(monkeypatch):
    monkeypatch.setenv("MODEL_CONTEXT_TOKENS", "6000")
    budget = InputBudget()

    @tool
    def search(query: str) -> str:
        """Search evidence with a query."""
        return ""

    protected = [SystemMessage(content=f"Current evidence [Source: {URL}]")]
    messages = [SystemMessage(content="persona " * 2000), HumanMessage(content="query " * 5000)]
    fitted = budget.fit(messages, [search], protected=protected)
    assert budget.size(fitted, [search]) <= budget.limit
    assert fitted[-1] == protected[0]
    assert URL not in clip(f"text [Source: {URL}]", 25)


def test_postgres_configuration_fails_clearly(monkeypatch):
    from qubettera.agents.agent.checkpoint import get_checkpointer
    monkeypatch.setenv("CHECKPOINT_BACKEND", "postgres")
    monkeypatch.delenv("PGHOST", raising=False)
    with pytest.raises(ValueError, match="PGHOST"):
        with get_checkpointer():
            pass
    monkeypatch.setenv("CHECKPOINT_BACKEND", "typo")
    with pytest.raises(ValueError, match="CHECKPOINT_BACKEND"):
        with get_checkpointer():
            pass


def test_postgres_lifecycle_reopens_threads_and_closes_on_failure(monkeypatch):
    from qubettera.agents.agent import checkpoint
    events = []
    saver = MemorySaver()

    @contextmanager
    def opened():
        events.append("open")
        try:
            yield saver
        finally:
            events.append("close")

    monkeypatch.setenv("CHECKPOINT_BACKEND", "postgres")
    for name in checkpoint._REQUIRED_PG_VARS:
        monkeypatch.setenv(name, "configured")
    monkeypatch.setattr(checkpoint, "open_postgres_checkpointer", opened)
    model = ScriptedModel()
    model.responses = [AIMessage(content="No supporting evidence is available.") for _ in range(2)]
    with Week2AgentRuntime(model=model, tools=[]) as runtime:
        runtime.run_turn(make_request(0))
    with pytest.raises(RuntimeError, match="planned"):
        with Week2AgentRuntime(model=model, tools=[]) as runtime:
            runtime.run_turn(make_request(1))
            state = runtime.graph.get_state({"configurable": {"thread_id": "discussion-7:dr_aris"}}).values
            assert sum(m.type == "human" for m in state["messages"]) == 2
            raise RuntimeError("planned")
    assert events == ["open", "close", "open", "close"]


def test_exact_source_identity_and_missing_support():
    assert not citation_errors(f"Claim [Source: {URL}]", EVIDENCE)
    assert citation_errors(f"Claim [Source: {URL}/]", EVIDENCE)
    assert citation_errors(f"Claim [Source: {URL}]", ())
    assert not citation_errors("No supporting evidence is available.", ())


def test_moderator_is_neutral_and_keeps_all_final_participants(monkeypatch):
    from qubettera.discussion.models import RoutedMessage
    monkeypatch.setenv("MODEL_CONTEXT_TOKENS", "8000")
    model = ScriptedModel()
    model.responses = [AIMessage(content=f"Recommendation with uncertainty [Source: {URL}]")]
    messages = tuple(RoutedMessage(message_id=str(i), discussion_id="discussion-7", phase="discussion",
        round_number=3, sequence_number=i, sender_id=f"participant-{i}", recipient_ids=(),
        content="Long opinion " * 2000 + f" [Source: {URL}]", opinion="opinion",
        warnings=("unresolved source identity",)) for i in range(5))
    with Week2AgentRuntime(model=model, tools=[]) as runtime:
        result = runtime.run_turn(replace(make_request(3), phase="synthesis", agent_id="moderator",
            incoming_messages=messages, evidence=EVIDENCE))
    assert not result.metadata["warnings"]
    prompt = "\n".join(m.content for m in model.invocations[0])
    assert "neutral moderator" in prompt
    assert "Background:" not in prompt
    assert all(f"participant-{i}" in prompt for i in range(5))
    assert "unresolved source identity" in prompt


def test_runtime_closes_checkpoint_if_graph_compilation_fails(monkeypatch):
    from qubettera.agents.agent import checkpoint, graph
    events = []

    @contextmanager
    def opened():
        try:
            yield MemorySaver()
        finally:
            events.append("closed")

    def fail(**kwargs):
        raise RuntimeError("compile failed")

    monkeypatch.setattr(checkpoint, "get_checkpointer", opened)
    monkeypatch.setattr(graph, "build_graph", fail)
    with pytest.raises(RuntimeError, match="compile failed"):
        Week2AgentRuntime(model=ScriptedModel(), tools=[])
    assert events == ["closed"]


def test_small_history_does_not_trigger_unnecessary_summary():
    model = ScriptedModel()
    model.responses = [AIMessage(content="No supporting evidence is available.") for _ in range(7)]
    with Week2AgentRuntime(model=model, tools=[]) as runtime:
        for index in range(7):
            runtime.run_turn(make_request(index))
    assert len(model.invocations) == 7


def test_postgres_saver_setup_and_exit(monkeypatch):
    from qubettera.agents.agent.checkpoint import open_postgres_checkpointer
    from langgraph.checkpoint.postgres import PostgresSaver
    events = []

    class Saver:
        def setup(self):
            events.append("setup")

    @contextmanager
    def connect(conninfo):
        assert conninfo == "test-connection"
        events.append("open")
        try:
            yield Saver()
        finally:
            events.append("close")

    monkeypatch.setattr(PostgresSaver, "from_conn_string", connect)
    with pytest.raises(RuntimeError, match="planned"):
        with open_postgres_checkpointer("test-connection"):
            raise RuntimeError("planned")
    assert events == ["open", "setup", "close"]


def test_transport_timeout_does_not_launch_second_generation():
    import httpx
    from qubettera.agents.agent.graph import build_graph
    from qubettera.agents.personas import load_persona

    class TimedOut:
        calls = 0

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            self.calls += 1
            raise httpx.ReadTimeout("The read operation timed out")

    model = TimedOut()
    graph = build_graph(checkpointer=MemorySaver(), model=model, tools=[])
    with pytest.raises(RuntimeError, match="Generation model connection failed"):
        graph.invoke({"messages": [HumanMessage(content="Question")],
                      "persona": load_persona("dr_aris"),
                      "discussion_mode": True},
                     config={"configurable": {"thread_id": "timeout-once"}})
    assert model.calls == 1


def test_live_cli_defaults_to_one_worker_and_accepts_override(monkeypatch, tmp_path):
    from qubettera import cli
    from qubettera.discussion import orchestrator, retrieval_provider, week2_adapter

    workers = []

    class Runtime:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Orchestrator:
        def __init__(self, **kwargs):
            workers.append(kwargs["max_workers"])

        def run(self, config):
            return type("Result", (), {"discussion_id": "test", "status": "completed", "messages": ()})()

    monkeypatch.setattr(week2_adapter, "Week2AgentRuntime", Runtime)
    monkeypatch.setattr(retrieval_provider, "TeamRetrievalProvider", lambda: object())
    monkeypatch.setattr(orchestrator, "DiscussionOrchestrator", Orchestrator)
    monkeypatch.setenv("LLM_PROVIDER", "kaggle")
    base = ["discuss", "run", "--mode", "live", "--output-dir", str(tmp_path)]
    assert cli.main(base) == 0
    assert cli.main([*base, "--max-workers", "3"]) == 0
    assert workers == [1, 3]


def test_wandb_live_cli_uses_parallel_default(monkeypatch, tmp_path):
    from qubettera import cli
    from qubettera.discussion import orchestrator, retrieval_provider, week2_adapter

    workers = []

    class Runtime:
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class Orchestrator:
        def __init__(self, **kwargs): workers.append(kwargs["max_workers"])
        def run(self, config):
            return type("Result", (), {"discussion_id": "test", "status": "completed", "messages": ()})()

    monkeypatch.setenv("LLM_PROVIDER", "wandb")
    monkeypatch.setattr(week2_adapter, "Week2AgentRuntime", Runtime)
    monkeypatch.setattr(retrieval_provider, "TeamRetrievalProvider", lambda: object())
    monkeypatch.setattr(orchestrator, "DiscussionOrchestrator", Orchestrator)
    assert cli.main(["discuss", "run", "--mode", "live", "--output-dir", str(tmp_path)]) == 0
    assert workers == [None]
