import pytest

from qubettera.discussion.agent_graph import AgentGraph
from qubettera.discussion.models import RoutedMessage
from qubettera.discussion.router import filter_delivered, get_recipients, route_message


def make_graph(edges):
    nodes = sorted({node for edge in edges for node in edge})
    return AgentGraph(nodes=tuple(nodes), edges=tuple(edges))


def test_get_recipients_follows_configured_edges():
    graph = make_graph([("a", "b"), ("a", "d"), ("b", "a"), ("d", "a")])

    assert get_recipients("a", graph) == ("b", "d")
    assert "c" not in get_recipients("a", graph)


def test_get_recipients_reflects_edge_removal():
    graph_with_edge = make_graph([("a", "b"), ("b", "a")])
    assert get_recipients("a", graph_with_edge) == ("b",)

    graph_without_edge = AgentGraph(
        nodes=graph_with_edge.nodes,
        edges=tuple(edge for edge in graph_with_edge.edges if edge != ("a", "b")),
    )
    assert "b" not in get_recipients("a", graph_without_edge)


def test_filter_delivered_only_returns_messages_routed_to_recipient():
    message_to_b = RoutedMessage(
        message_id="1",
        discussion_id="d",
        phase="discussion",
        round_number=1,
        sequence_number=1,
        sender_id="a",
        recipient_ids=("b",),
        content="hello",
        opinion="hello",
    )
    message_to_c = RoutedMessage(
        message_id="2",
        discussion_id="d",
        phase="discussion",
        round_number=1,
        sequence_number=2,
        sender_id="a",
        recipient_ids=("c",),
        content="hi",
        opinion="hi",
    )

    delivered = filter_delivered((message_to_b, message_to_c), "b")

    assert delivered == (message_to_b,)


def test_route_message_recomputes_recipient_ids_from_graph():
    graph = make_graph([("a", "b"), ("b", "a")])
    stale_message = RoutedMessage(
        message_id="1",
        discussion_id="d",
        phase="discussion",
        round_number=1,
        sequence_number=1,
        sender_id="a",
        recipient_ids=("someone-stale",),
        content="hello",
        opinion="hello",
    )

    rerouted = route_message(stale_message, graph)

    assert rerouted.recipient_ids == ("b",)
    assert rerouted.sender_id == "a"


def test_get_recipients_rejects_unknown_sender():
    graph = make_graph([("a", "b"), ("b", "a")])
    with pytest.raises(KeyError):
        get_recipients("unknown", graph)
