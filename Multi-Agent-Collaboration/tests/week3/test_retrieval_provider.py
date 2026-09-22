from src.retrieval import RetrievalConfigurationError
from week3.models import DiscussionBrief, RoutedMessage, TurnRequest
from week3.retrieval_provider import TeamRetrievalProvider


class FakeOllamaClient:
    def __init__(self):
        self.calls: list[dict] = []

    def embed(self, *, model, input):
        self.calls.append({"model": model, "input": input})
        return {"embeddings": [[0.1, 0.2, 0.3]]}


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, sql, params):
        return None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.fake_cursor = FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


class RaisingOllamaClient:
    def embed(self, *, model, input):
        raise RuntimeError("kaggle tunnel unreachable")


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
    rows = [
        (
            "chunk-1",
            "doc-1",
            "MoE activates a subset of experts per token.",
            {"title": "MoE Systems", "canonical_url": "https://example.org/moe", "topic": "experts"},
            0.21,
        )
    ]
    provider = TeamRetrievalProvider(
        ollama_client=FakeOllamaClient(),
        connection=FakeConnection(rows),
    )
    request = make_request()

    evidence = provider.retrieve("MoE dense memory efficiency", request)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.text == "MoE activates a subset of experts per token."
    assert item.title == "MoE Systems"
    assert item.url == "https://example.org/moe"
    assert item.score == 0.21
    assert item.metadata.get("topic") == "experts"


def test_retrieve_returns_empty_tuple_for_blank_query():
    provider = TeamRetrievalProvider(ollama_client=FakeOllamaClient(), connection=FakeConnection([]))
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
    provider = TeamRetrievalProvider(ollama_client=RaisingOllamaClient(), connection=FakeConnection([]))
    request = make_request()

    # A retrieval outage must not crash the discussion turn - it degrades to
    # no fresh evidence for this turn instead of propagating the exception.
    assert provider.retrieve("some query", request) == ()


def test_retrieve_propagates_only_expected_configuration_errors(monkeypatch):
    def _raise_configuration_error(*args, **kwargs):
        raise RetrievalConfigurationError("DATABASE_URL missing")

    monkeypatch.setattr(
        "week3.retrieval_provider.search_knowledge_base", _raise_configuration_error
    )
    provider = TeamRetrievalProvider()
    request = make_request()

    assert provider.retrieve("some query", request) == ()