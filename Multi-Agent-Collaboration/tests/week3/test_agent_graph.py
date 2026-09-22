import json

import pytest

from week3.agent_graph import AgentGraph, GraphConfigurationError


def test_supplied_graph_is_directed_strongly_connected_and_reproducible():
    graph = AgentGraph.from_json("configs/agent_graph.json")

    assert graph.is_strongly_connected()
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 10
    assert graph.has_edge("dr_aris", "prof_elena")
    assert graph.recipients("dr_aris") == ("prof_elena", "grad_student")
    assert graph.senders("dr_aris") == ("prof_elena", "grad_student")
    assert AgentGraph.from_dict(graph.to_dict()) == graph


def test_one_way_chain_is_rejected_because_information_cannot_return():
    with pytest.raises(GraphConfigurationError, match="not strongly connected"):
        AgentGraph.from_dict(
            {
                "nodes": ["a", "b", "c"],
                "edges": [["a", "b"], ["b", "c"]],
            }
        )


def test_unknown_duplicate_and_self_edges_are_rejected():
    invalid_edges = (
        [["a", "missing"], ["missing", "a"]],
        [["a", "b"], ["a", "b"], ["b", "a"]],
        [["a", "a"], ["a", "b"], ["b", "a"]],
    )
    for edges in invalid_edges:
        with pytest.raises(GraphConfigurationError):
            AgentGraph.from_dict({"nodes": ["a", "b"], "edges": edges})


def test_removing_an_edge_blocks_that_direct_route():
    payload = json.loads(open("configs/agent_graph.json", encoding="utf-8").read())
    payload["edges"].remove(["dr_aris", "prof_elena"])
    graph = AgentGraph.from_dict(payload)

    assert not graph.has_edge("dr_aris", "prof_elena")
    assert "prof_elena" not in graph.recipients("dr_aris")
    assert graph.is_strongly_connected()
