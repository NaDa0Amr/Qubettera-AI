"""Programmatic graph construction and topology factories.

``GraphBuilder`` provides a mutable, fluent API for assembling an
``AgentGraph``.  Topology classmethods (``ring``, ``fully_connected``,
``star``, ``from_persona_ids``) generate common topologies with strong
connectivity guaranteed.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from qubettera.discussion.agent_graph import AgentGraph, GraphConfigurationError


class GraphBuilder:
    """Mutable builder that produces an immutable ``AgentGraph``.

    Example::

        graph = (
            GraphBuilder()
            .add_nodes(["a", "b", "c"])
            .add_edge("a", "b")
            .add_edge("b", "c")
            .add_edge("c", "a")
            .build()
        )
    """

    def __init__(self) -> None:
        self._nodes: list[str] = []
        self._edges: list[tuple[str, str]] = []

    # -- Fluent mutators ---------------------------------------------------

    def add_node(self, node_id: str) -> "GraphBuilder":
        """Register a single agent node."""
        if not isinstance(node_id, str) or not node_id.strip():
            raise GraphConfigurationError("Node ID must be a non-blank string.")
        if node_id in self._nodes:
            raise GraphConfigurationError(f"Duplicate node: {node_id!r}")
        self._nodes.append(node_id)
        return self

    def add_nodes(self, node_ids: Iterable[str]) -> "GraphBuilder":
        """Register multiple agent nodes."""
        for node_id in node_ids:
            self.add_node(node_id)
        return self

    def add_edge(self, source: str, target: str) -> "GraphBuilder":
        """Add a single directed edge."""
        if source == target:
            raise GraphConfigurationError(f"Self-edge {source!r} -> {target!r} is not allowed.")
        if (source, target) in self._edges:
            raise GraphConfigurationError(f"Duplicate edge: {source!r} -> {target!r}.")
        # Auto-register nodes that appear in edges but were not explicitly added
        if source not in self._nodes:
            self._nodes.append(source)
        if target not in self._nodes:
            self._nodes.append(target)
        self._edges.append((source, target))
        return self

    def add_edges(self, pairs: Iterable[tuple[str, str]]) -> "GraphBuilder":
        """Add multiple directed edges."""
        for source, target in pairs:
            self.add_edge(source, target)
        return self

    def remove_edge(self, source: str, target: str) -> "GraphBuilder":
        """Remove a directed edge."""
        try:
            self._edges.remove((source, target))
        except ValueError:
            raise GraphConfigurationError(
                f"Edge {source!r} -> {target!r} does not exist."
            ) from None
        return self

    def build(self) -> AgentGraph:
        """Validate and return an immutable ``AgentGraph``.

        Raises ``GraphConfigurationError`` if the graph has fewer than two
        nodes or is not strongly connected.
        """
        graph = AgentGraph(
            nodes=tuple(self._nodes),
            edges=tuple(self._edges),
        )
        graph.validate()
        return graph

    # -- Topology factories ------------------------------------------------

    @classmethod
    def ring(cls, node_ids: Sequence[str]) -> AgentGraph:
        """Bidirectional ring: each node connects to its two neighbors.

        This is the topology used by ``configs/agent_graph.json``.  For *N*
        nodes it produces *2N* directed edges.

        ::

            A --> B
            ^    |
            |    v
            D <-- C
        """
        ids = list(node_ids)
        if len(ids) < 2:
            raise GraphConfigurationError("A ring requires at least two nodes.")
        builder = cls().add_nodes(ids)
        for i in range(len(ids)):
            next_i = (i + 1) % len(ids)
            if (ids[i], ids[next_i]) not in builder._edges:
                builder.add_edge(ids[i], ids[next_i])
            if (ids[next_i], ids[i]) not in builder._edges:
                builder.add_edge(ids[next_i], ids[i])
        return builder.build()

    @classmethod
    def fully_connected(cls, node_ids: Sequence[str]) -> AgentGraph:
        """Complete directed graph: every node has an edge to every other.

        For *N* nodes this produces *N * (N - 1)* directed edges.
        """
        ids = list(node_ids)
        if len(ids) < 2:
            raise GraphConfigurationError(
                "A fully connected graph requires at least two nodes."
            )
        builder = cls().add_nodes(ids)
        for source in ids:
            for target in ids:
                if source != target:
                    builder.add_edge(source, target)
        return builder.build()

    @classmethod
    def star(cls, hub: str, spokes: Sequence[str]) -> AgentGraph:
        """Hub-and-spoke with strong connectivity guarantee.

        Every spoke has bidirectional edges with the hub, and the spokes
        are connected in a directed ring so that information can flow
        between any two spokes without going through the hub.
        """
        spoke_list = list(spokes)
        if not spoke_list:
            raise GraphConfigurationError("A star graph requires at least one spoke.")
        if hub in spoke_list:
            raise GraphConfigurationError(f"Hub {hub!r} must not appear in spokes.")

        builder = cls().add_node(hub).add_nodes(spoke_list)

        # Bidirectional hub <-> spoke edges
        for spoke in spoke_list:
            builder.add_edge(hub, spoke)
            builder.add_edge(spoke, hub)

        # Ring among spokes for strong connectivity (only needed for >= 2 spokes)
        if len(spoke_list) >= 2:
            for i in range(len(spoke_list)):
                next_i = (i + 1) % len(spoke_list)
                builder.add_edge(spoke_list[i], spoke_list[next_i])

        return builder.build()

    @classmethod
    def from_persona_ids(cls, persona_ids: Sequence[str]) -> AgentGraph:
        """Generate a topology from persona expertise overlap.

        Agents whose ``expertise`` lists share at least one keyword receive
        bidirectional edges.  If the resulting graph is not strongly
        connected, a ring through the unconnected nodes is added as a
        fallback to guarantee the strong connectivity invariant.
        """
        from qubettera.agents.personas import load_persona

        ids = list(persona_ids)
        if len(ids) < 2:
            raise GraphConfigurationError(
                "Persona-based graph requires at least two persona IDs."
            )

        # Load expertise for each persona
        expertise_map: dict[str, set[str]] = {}
        for pid in ids:
            persona = load_persona(pid)
            expertise_map[pid] = {
                keyword.strip().lower() for keyword in persona.expertise
            }

        builder = cls().add_nodes(ids)

        # Add bidirectional edges between personas with overlapping expertise
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if expertise_map[a] & expertise_map[b]:
                    builder.add_edge(a, b)
                    builder.add_edge(b, a)

        # Patch connectivity: add a directed ring through nodes if needed
        _ensure_strongly_connected(builder, ids)

        return builder.build()


def _ensure_strongly_connected(builder: GraphBuilder, ids: list[str]) -> None:
    """Add minimal ring edges to make the builder's graph strongly connected.

    Walks the node list in order and adds forward edges (ids[i] -> ids[i+1])
    wherever one is missing, then does the same in reverse (ids[i+1] -> ids[i]).
    This guarantees a Hamiltonian cycle exists, which is sufficient for strong
    connectivity.
    """
    for i in range(len(ids)):
        next_i = (i + 1) % len(ids)
        if (ids[i], ids[next_i]) not in builder._edges:
            builder.add_edge(ids[i], ids[next_i])
        if (ids[next_i], ids[i]) not in builder._edges:
            builder.add_edge(ids[next_i], ids[i])
