"""Tests for src.graph_builder and the AgentGraph visualization methods."""

import pytest

from qubettera.discussion.agent_graph import AgentGraph, GraphConfigurationError
from qubettera.agents.graph_builder import GraphBuilder


# ---------------------------------------------------------------------------
# GraphBuilder -- manual construction
# ---------------------------------------------------------------------------


class TestGraphBuilderManual:
    def test_build_simple_cycle(self):
        graph = (
            GraphBuilder()
            .add_nodes(["a", "b", "c"])
            .add_edge("a", "b")
            .add_edge("b", "c")
            .add_edge("c", "a")
            .add_edge("a", "c")
            .add_edge("b", "a")
            .add_edge("c", "b")
            .build()
        )
        assert isinstance(graph, AgentGraph)
        assert graph.is_strongly_connected()
        assert set(graph.nodes) == {"a", "b", "c"}
        assert len(graph.edges) == 6

    def test_auto_registers_nodes_from_edges(self):
        graph = (
            GraphBuilder()
            .add_edge("x", "y")
            .add_edge("y", "x")
            .build()
        )
        assert set(graph.nodes) == {"x", "y"}

    def test_add_edges_batch(self):
        graph = (
            GraphBuilder()
            .add_edges([("a", "b"), ("b", "c"), ("c", "a"), ("b", "a"), ("c", "b"), ("a", "c")])
            .build()
        )
        assert graph.is_strongly_connected()
        assert len(graph.edges) == 6

    def test_remove_edge(self):
        builder = GraphBuilder().add_edges([("a", "b"), ("b", "a"), ("a", "c"), ("c", "a"), ("b", "c"), ("c", "b")])
        builder.remove_edge("a", "c")
        graph = builder.build()
        assert not graph.has_edge("a", "c")
        assert graph.is_strongly_connected()  # still connected via a->b->c

    def test_remove_nonexistent_edge_raises(self):
        builder = GraphBuilder().add_edge("a", "b").add_edge("b", "a")
        with pytest.raises(GraphConfigurationError, match="does not exist"):
            builder.remove_edge("a", "c")

    def test_duplicate_node_raises(self):
        with pytest.raises(GraphConfigurationError, match="Duplicate node"):
            GraphBuilder().add_node("a").add_node("a")

    def test_blank_node_raises(self):
        with pytest.raises(GraphConfigurationError, match="non-blank"):
            GraphBuilder().add_node("")

    def test_self_edge_raises(self):
        with pytest.raises(GraphConfigurationError, match="Self-edge"):
            GraphBuilder().add_edge("a", "a")

    def test_duplicate_edge_raises(self):
        with pytest.raises(GraphConfigurationError, match="Duplicate edge"):
            GraphBuilder().add_edge("a", "b").add_edge("a", "b")

    def test_build_with_fewer_than_two_nodes_raises(self):
        with pytest.raises(GraphConfigurationError, match="at least two"):
            GraphBuilder().add_node("solo").build()

    def test_build_without_strong_connectivity_raises(self):
        with pytest.raises(GraphConfigurationError, match="not strongly connected"):
            GraphBuilder().add_edge("a", "b").add_edge("b", "c").build()


# ---------------------------------------------------------------------------
# Topology factories
# ---------------------------------------------------------------------------


class TestRingFactory:
    def test_ring_two_nodes(self):
        graph = GraphBuilder.ring(["a", "b"])
        assert graph.is_strongly_connected()
        assert len(graph.edges) == 2
        assert graph.has_edge("a", "b")
        assert graph.has_edge("b", "a")

    def test_ring_five_nodes(self):
        ids = ["n1", "n2", "n3", "n4", "n5"]
        graph = GraphBuilder.ring(ids)
        assert graph.is_strongly_connected()
        assert len(graph.nodes) == 5
        assert len(graph.edges) == 10  # 2 * 5

    def test_ring_too_few_nodes_raises(self):
        with pytest.raises(GraphConfigurationError, match="at least two"):
            GraphBuilder.ring(["lonely"])

    def test_ring_matches_existing_config(self):
        """The ring factory should produce the same topology as agent_graph.json."""
        ids = ["dr_aris", "prof_elena", "systems_specialist", "hybrid_architect", "grad_student"]
        ring_graph = GraphBuilder.ring(ids)
        json_graph = AgentGraph.from_json("resources/configs/agent_graph.json")

        assert set(ring_graph.nodes) == set(json_graph.nodes)
        assert set(ring_graph.edges) == set(json_graph.edges)


class TestFullyConnectedFactory:
    def test_fully_connected_three_nodes(self):
        graph = GraphBuilder.fully_connected(["a", "b", "c"])
        assert graph.is_strongly_connected()
        assert len(graph.edges) == 6  # 3 * 2

    def test_fully_connected_edge_count(self):
        ids = ["w", "x", "y", "z"]
        graph = GraphBuilder.fully_connected(ids)
        assert len(graph.edges) == 12  # 4 * 3

    def test_fully_connected_two_nodes(self):
        graph = GraphBuilder.fully_connected(["a", "b"])
        assert graph.is_strongly_connected()
        assert len(graph.edges) == 2

    def test_fully_connected_too_few_raises(self):
        with pytest.raises(GraphConfigurationError, match="at least two"):
            GraphBuilder.fully_connected(["alone"])


class TestStarFactory:
    def test_star_basic(self):
        graph = GraphBuilder.star(hub="center", spokes=["s1", "s2", "s3"])
        assert graph.is_strongly_connected()
        assert "center" in graph.nodes
        # Hub has bidirectional edges to all spokes
        assert graph.has_edge("center", "s1")
        assert graph.has_edge("s1", "center")

    def test_star_single_spoke(self):
        graph = GraphBuilder.star(hub="h", spokes=["s"])
        assert graph.is_strongly_connected()
        assert len(graph.nodes) == 2
        assert graph.has_edge("h", "s")
        assert graph.has_edge("s", "h")

    def test_star_spokes_form_ring(self):
        graph = GraphBuilder.star(hub="hub", spokes=["a", "b", "c"])
        # Spokes should have a directed ring: a->b, b->c, c->a
        assert graph.has_edge("a", "b")
        assert graph.has_edge("b", "c")
        assert graph.has_edge("c", "a")

    def test_star_no_spokes_raises(self):
        with pytest.raises(GraphConfigurationError, match="at least one spoke"):
            GraphBuilder.star(hub="h", spokes=[])

    def test_star_hub_in_spokes_raises(self):
        with pytest.raises(GraphConfigurationError, match="must not appear in spokes"):
            GraphBuilder.star(hub="h", spokes=["h", "a"])


class TestPersonaFactory:
    def test_persona_graph_is_strongly_connected(self):
        """The 5 discussion personas must produce a strongly connected graph."""
        ids = ["dr_aris", "prof_elena", "systems_specialist", "hybrid_architect", "grad_student"]
        graph = GraphBuilder.from_persona_ids(ids)
        assert graph.is_strongly_connected()
        assert set(graph.nodes) == set(ids)

    def test_persona_graph_too_few_raises(self):
        with pytest.raises(GraphConfigurationError, match="at least two"):
            GraphBuilder.from_persona_ids(["dr_aris"])

    def test_persona_graph_has_expertise_based_edges(self):
        """Personas with overlapping expertise should have direct edges."""
        ids = ["dr_aris", "prof_elena", "systems_specialist", "hybrid_architect", "grad_student"]
        graph = GraphBuilder.from_persona_ids(ids)
        # All these personas have AI/ML/architecture related expertise
        # At minimum, the graph should have more than just a ring's edges
        # if personas share expertise keywords
        assert len(graph.edges) >= 10  # at least a ring worth


# ---------------------------------------------------------------------------
# AgentGraph visualization methods
# ---------------------------------------------------------------------------


class TestRenderAscii:
    def test_render_ascii_contains_all_nodes(self):
        graph = GraphBuilder.ring(["alice", "bob", "carol"])
        output = graph.render_ascii()
        assert "alice" in output
        assert "bob" in output
        assert "carol" in output

    def test_render_ascii_contains_summary(self):
        graph = GraphBuilder.ring(["a", "b", "c"])
        output = graph.render_ascii()
        assert "Nodes: 3" in output
        assert "Edges: 6" in output
        assert "Strongly connected: True" in output

    def test_render_ascii_shows_adjacency(self):
        graph = GraphBuilder.ring(["x", "y"])
        output = graph.render_ascii()
        assert "x -> y" in output
        assert "y -> x" in output

    def test_render_ascii_from_json_config(self):
        graph = AgentGraph.from_json("resources/configs/agent_graph.json")
        output = graph.render_ascii()
        assert "Agent Communication Graph" in output
        assert "dr_aris" in output
        assert "Nodes: 5" in output
        assert "Edges: 10" in output


class TestDescribe:
    def test_describe_returns_expected_keys(self):
        graph = GraphBuilder.ring(["a", "b", "c"])
        desc = graph.describe()
        expected_keys = {
            "nodes", "edges", "adjacency", "is_strongly_connected",
            "node_count", "edge_count", "in_degree", "out_degree",
        }
        assert set(desc.keys()) == expected_keys

    def test_describe_values(self):
        graph = GraphBuilder.ring(["a", "b"])
        desc = graph.describe()
        assert desc["node_count"] == 2
        assert desc["edge_count"] == 2
        assert desc["is_strongly_connected"] is True
        assert desc["in_degree"]["a"] == 1
        assert desc["out_degree"]["a"] == 1

    def test_describe_fully_connected(self):
        graph = GraphBuilder.fully_connected(["a", "b", "c"])
        desc = graph.describe()
        assert desc["node_count"] == 3
        assert desc["edge_count"] == 6
        # In a fully connected graph, every node has degree N-1
        for node in desc["nodes"]:
            assert desc["in_degree"][node] == 2
            assert desc["out_degree"][node] == 2

    def test_describe_adjacency_matches_graph(self):
        graph = AgentGraph.from_json("resources/configs/agent_graph.json")
        desc = graph.describe()
        for node in graph.nodes:
            assert desc["adjacency"][node] == list(graph.adjacency[node])
