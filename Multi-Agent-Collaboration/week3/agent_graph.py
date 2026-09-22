"""Task 1: directed communication graph for Week 3 agents."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class GraphConfigurationError(ValueError):
    """Raised when a discussion topology is invalid."""


@dataclass(frozen=True)
class AgentGraph:
    """Immutable, inspectable directed agent graph.

    An edge (A, B) means that a message sent by A is delivered directly to B.
    Strong connectivity means every node can reach every other through one or
    more directed edges.
    """

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentGraph":
        raw_nodes = payload.get("nodes")
        raw_edges = payload.get("edges")
        if not isinstance(raw_nodes, list):
            raise GraphConfigurationError("Graph 'nodes' must be a list.")
        if not isinstance(raw_edges, list):
            raise GraphConfigurationError("Graph 'edges' must be a list.")

        nodes = tuple(raw_nodes)
        edges: list[tuple[str, str]] = []
        for index, edge in enumerate(raw_edges):
            if isinstance(edge, dict):
                source, target = edge.get("source"), edge.get("target")
            elif isinstance(edge, (list, tuple)) and len(edge) == 2:
                source, target = edge
            else:
                raise GraphConfigurationError(
                    f"Edge {index} must be [source, target] or an object with source and target."
                )
            edges.append((source, target))

        graph = cls(nodes=nodes, edges=tuple(edges))
        graph.validate()
        return graph

    @classmethod
    def from_json(cls, path: str | Path) -> "AgentGraph":
        config_path = Path(path)
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise GraphConfigurationError(f"Graph file does not exist: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise GraphConfigurationError(f"Graph file is not valid JSON: {config_path}") from exc
        return cls.from_dict(payload)

    @property
    def adjacency(self) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {node: [] for node in self.nodes}
        for source, target in self.edges:
            result[source].append(target)
        return {node: tuple(targets) for node, targets in result.items()}

    @property
    def reverse_adjacency(self) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {node: [] for node in self.nodes}
        for source, target in self.edges:
            result[target].append(source)
        return {node: tuple(sources) for node, sources in result.items()}

    def recipients(self, sender_id: str) -> tuple[str, ...]:
        self._require_node(sender_id)
        return self.adjacency[sender_id]

    def senders(self, recipient_id: str) -> tuple[str, ...]:
        self._require_node(recipient_id)
        return self.reverse_adjacency[recipient_id]

    def has_edge(self, source: str, target: str) -> bool:
        return (source, target) in self.edges

    def validate_participants(self, participant_ids: Iterable[str]) -> None:
        participants = tuple(participant_ids)
        if set(participants) != set(self.nodes) or len(participants) != len(self.nodes):
            raise GraphConfigurationError(
                "Discussion participants must match the graph nodes exactly. "
                f"participants={participants!r}, graph_nodes={self.nodes!r}"
            )

    def is_strongly_connected(self) -> bool:
        if not self.nodes:
            return False
        start = self.nodes[0]
        return (
            self._reachable(start, self.adjacency) == set(self.nodes)
            and self._reachable(start, self.reverse_adjacency) == set(self.nodes)
        )

    def validate(self) -> None:
        if len(self.nodes) < 2:
            raise GraphConfigurationError("A discussion graph requires at least two nodes.")
        if any(not isinstance(node, str) or not node.strip() for node in self.nodes):
            raise GraphConfigurationError("Every graph node must be a non-blank string.")
        if len(set(self.nodes)) != len(self.nodes):
            raise GraphConfigurationError("Graph nodes must be unique.")
        if not self.edges:
            raise GraphConfigurationError("A discussion graph requires directed edges.")

        known = set(self.nodes)
        seen: set[tuple[str, str]] = set()
        for source, target in self.edges:
            if not isinstance(source, str) or not isinstance(target, str):
                raise GraphConfigurationError("Edge endpoints must be strings.")
            if source not in known or target not in known:
                raise GraphConfigurationError(f"Edge {source!r} -> {target!r} references an unknown node.")
            if source == target:
                raise GraphConfigurationError(f"Self-edge {source!r} -> {target!r} is not allowed.")
            if (source, target) in seen:
                raise GraphConfigurationError(f"Duplicate edge {source!r} -> {target!r}.")
            seen.add((source, target))

        if not self.is_strongly_connected():
            raise GraphConfigurationError("The directed agent graph is not strongly connected.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "directed": True,
            "nodes": list(self.nodes),
            "edges": [[source, target] for source, target in self.edges],
        }

    def render_ascii(self) -> str:
        """Human-readable adjacency list with summary statistics."""
        adj = self.adjacency
        lines = ["Agent Communication Graph", "=" * 40]
        for node in self.nodes:
            targets = adj[node]
            arrow = " -> " + ", ".join(targets) if targets else " -> (none)"
            lines.append(f"  {node}{arrow}")
        lines.append("-" * 40)
        lines.append(
            f"  Nodes: {len(self.nodes)}  |  Edges: {len(self.edges)}  |  "
            f"Strongly connected: {self.is_strongly_connected()}"
        )
        return "\n".join(lines)

    def describe(self) -> dict[str, Any]:
        """Rich description dict for programmatic inspection."""
        adj = self.adjacency
        rev = self.reverse_adjacency
        return {
            "nodes": list(self.nodes),
            "edges": [[s, t] for s, t in self.edges],
            "adjacency": {node: list(targets) for node, targets in adj.items()},
            "is_strongly_connected": self.is_strongly_connected(),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "in_degree": {node: len(rev[node]) for node in self.nodes},
            "out_degree": {node: len(adj[node]) for node in self.nodes},
        }

    def _require_node(self, node: str) -> None:
        if node not in self.nodes:
            raise KeyError(f"Unknown agent ID: {node!r}")

    @staticmethod
    def _reachable(start: str, adjacency: dict[str, tuple[str, ...]]) -> set[str]:
        visited: set[str] = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(neighbor for neighbor in adjacency[node] if neighbor not in visited)
        return visited
