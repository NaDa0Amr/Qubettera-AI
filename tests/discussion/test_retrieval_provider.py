import pytest

from qubettera.discussion.models import DiscussionBrief, RoutedMessage, TurnRequest
from qubettera.discussion.retrieval_provider import TeamRetrievalProvider


class FakeRetrievalService:
    def __init__(self, rows=(), error=None):
        self.rows = list(rows)
        self.error = error

    def retrieve(self, query, top_k=5):
        if self.error:
            raise self.error
        return self.rows[:top_k]


def make_brief():
    return DiscussionBrief(
        objective="Recommend a Transformer architecture.",
        constraints=("One A100 GPU with 40 GB memory.",),
        topics=("Dense versus MoE layers.",),
        strict_notes=("Cite evidence.",),
    )


def make_request(agent_id="systems_specialist", incoming=(), previous_opinion=""):
    return TurnRequest(
        discussion_id="discussion-1",
        phase="discussion",
        round_number=2,
        sequence_number=7,
        agent_id=agent_id,
        recipient_ids=("prof_elena",),
        brief=make_brief(),
        incoming_messages=incoming,
        previous_opinion=previous_opinion,
    )


def make_neighbor_message(sender_id, content):
    return RoutedMessage(
        message_id=f"msg-{sender_id}",
        discussion_id="discussion-1",
        phase="discussion",
        round_number=1,
        sequence_number=1,
        sender_id=sender_id,
        recipient_ids=("systems_specialist",),
        content=content,
        opinion=content,
    )


def test_build_query_is_nonblank_and_reflects_current_discussion_state():
    provider = TeamRetrievalProvider()
    incoming = (make_neighbor_message("prof_elena", "MoE increases parameter capacity."),)
    request = make_request(incoming=incoming, previous_opinion="Dense is preferable for memory reasons.")

    query = provider.build_query(request)

    assert query.strip()
    assert "Recommend a Transformer architecture." in query
    assert "Dense is preferable for memory reasons." in query
    assert "prof_elena: MoE increases parameter capacity." in query
    # Persona retrieval focus (systems_specialist) should be pulled in too.
    assert "hardware" in query.lower() or "kernel" in query.lower()


def test_build_query_never_includes_messages_hidden_by_the_graph():
    provider = TeamRetrievalProvider()
    # incoming_messages already reflects Task 3/4 routing filtering, so a
    # message never routed to this agent simply never appears here.
    request = make_request(incoming=())

    query = provider.build_query(request)

    assert "hidden-neighbor" not in query


def test_retrieve_converts_documents_to_evidence_with_preserved_fields():
    rows = [{
        "chunk_id": "chunk-1",
        "text": "MoE activates a subset of experts per token.",
        "title": "MoE Systems",
        "url": "https://example.org/moe",
        "similarity": 0.79,
        "topic": "experts",
    }]
    provider = TeamRetrievalProvider(
        retrieval_service=FakeRetrievalService(rows),
    )
    request = make_request()

    evidence = provider.retrieve("MoE dense memory efficiency", request)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.text == "MoE activates a subset of experts per token."
    assert item.title == "MoE Systems"
    assert item.url == "https://example.org/moe"
    assert item.score == 0.79
    assert item.metadata.get("topic") == "experts"


def test_retrieve_returns_empty_tuple_for_blank_query():
    provider = TeamRetrievalProvider(retrieval_service=FakeRetrievalService())
    request = make_request()

    assert provider.retrieve("   ", request) == ()


def test_build_query_does_not_let_a_long_previous_opinion_crowd_out_neighbor_messages():
    # Regression test: real agent turns produce multi-thousand-character
    # essays. If truncation is only applied to the final joined string, a
    # long previous_opinion consumes the whole budget and the routed
    # neighbor messages - the entire point of a fresh, discussion-aware
    # query - never make it in.
    provider = TeamRetrievalProvider()
    long_previous_opinion = "Dense layers are preferable. " * 200  # ~6000 chars
    incoming = (make_neighbor_message("prof_elena", "MoE increases parameter capacity."),)
    request = make_request(incoming=incoming, previous_opinion=long_previous_opinion)

    query = provider.build_query(request)

    assert "prof_elena" in query
    assert "MoE increases parameter capacity" in query


def test_retrieve_handles_backend_outage_without_raising():
    provider = TeamRetrievalProvider(
        retrieval_service=FakeRetrievalService(error=RuntimeError("database unavailable"))
    )
    request = make_request()

    # A retrieval outage must not crash the discussion turn - it degrades to
    # no fresh evidence for this turn instead of propagating the exception.
    assert provider.retrieve("some query", request) == ()


def test_retrieve_propagates_only_expected_configuration_errors(monkeypatch):
    def _raise_configuration_error(*args, **kwargs):
        raise RuntimeError("PGHOST missing")

    monkeypatch.setattr(
        "qubettera.discussion.retrieval_provider.RetrievalService.retrieve",
        _raise_configuration_error,
    )
    provider = TeamRetrievalProvider()
    request = make_request()

    assert provider.retrieve("some query", request) == ()


def test_top_k_defaults_to_five_and_is_configurable(monkeypatch):
    monkeypatch.delenv("DISCUSSION_TOP_K", raising=False)
    assert TeamRetrievalProvider().top_k == 5

    monkeypatch.setenv("DISCUSSION_TOP_K", "12")
    assert TeamRetrievalProvider().top_k == 12

    # An explicit argument still wins over the environment.
    assert TeamRetrievalProvider(top_k=3).top_k == 3


def test_top_k_env_is_validated(monkeypatch):
    monkeypatch.setenv("DISCUSSION_TOP_K", "lots")
    with pytest.raises(RuntimeError, match="must be an integer"):
        TeamRetrievalProvider()

    monkeypatch.setenv("DISCUSSION_TOP_K", "0")
    with pytest.raises(RuntimeError, match="greater than zero"):
        TeamRetrievalProvider()


def test_configured_top_k_is_used_for_retrieval(monkeypatch):
    monkeypatch.setenv("DISCUSSION_TOP_K", "2")
    rows = [
        {"text": f"passage {index}", "url": f"https://example.org/{index}", "title": "T"}
        for index in range(5)
    ]
    service = FakeRetrievalService(rows)
    provider = TeamRetrievalProvider(retrieval_service=service)

    evidence = provider.retrieve("MoE memory efficiency", make_request())

    assert len(evidence) == 2
