"""
Graph utilities for multi-agent debate orchestration.
Supports loading graph configurations, building adjacency lists,
and validating strong connectivity (DFS).
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
except ImportError:
    jsonschema = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_graph_config(filepath: str = "personas/debate_graph.json") -> Dict:
    """
    Load the debate graph configuration from a JSON file.
    
    Args:
        filepath: Path to the graph configuration JSON.
        
    Returns:
        Dictionary with 'nodes' and 'edges' keys.
    """
    with open(filepath, "r") as f:
        return json.load(f)


def build_adjacency_list(nodes: List[str], edges: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """
    Build an undirected adjacency list from a list of nodes and edges.
    
    Args:
        nodes: List of node IDs.
        edges: List of [source, target] pairs.
        
    Returns:
        Dictionary mapping node ID -> list of neighbor IDs.
    """
    adjacency = {node: [] for node in nodes}
    for a, b in edges:
        if b not in adjacency[a]:
            adjacency[a].append(b)
        if a not in adjacency[b]:
            adjacency[b].append(a)
    return adjacency


def is_strongly_connected(adjacency: Dict[str, List[str]]) -> bool:
    """
    Check if an undirected graph is connected (strongly connected).
    Uses BFS/DFS starting from the first node.
    
    Args:
        adjacency: Dictionary mapping node ID -> list of neighbor IDs.
        
    Returns:
        True if the graph is connected, False otherwise.
    """
    if not adjacency:
        return True
    
    start = list(adjacency.keys())[0]
    visited = set()
    queue = deque([start])
    
    while queue:
        node = queue.popleft()
        visited.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                queue.append(neighbor)
    
    return len(visited) == len(adjacency)


def get_neighbor_ids(agent_id: str, adjacency: Dict[str, List[str]]) -> List[str]:
    """
    Get the neighbor IDs for a given agent.
    
    Args:
        agent_id: The ID of the agent.
        adjacency: Dictionary mapping node ID -> list of neighbor IDs.
        
    Returns:
        List of neighbor IDs (empty if agent not found).
    """
    return adjacency.get(agent_id, [])


def validate_graph_config(config: Dict) -> bool:
    """
    Validate that the graph configuration is well-formed.
    
    Args:
        config: Dictionary with 'nodes' and 'edges' keys.
        
    Returns:
        True if valid, raises ValueError otherwise.
    """
    if "nodes" not in config or not config["nodes"]:
        raise ValueError("Graph configuration must have non-empty 'nodes' list")
    
    if "edges" not in config:
        raise ValueError("Graph configuration must have 'edges' list")
    
    # Check all nodes in edges exist in nodes
    all_edges_nodes = set()
    for a, b in config["edges"]:
        all_edges_nodes.add(a)
        all_edges_nodes.add(b)
    
    missing_nodes = all_edges_nodes - set(config["nodes"])
    if missing_nodes:
        raise ValueError(f"Edges reference unknown nodes: {missing_nodes}")
    
    # Build adjacency and check connectivity
    adjacency = build_adjacency_list(config["nodes"], config["edges"])
    if not is_strongly_connected(adjacency):
        raise ValueError("Graph is not strongly connected (some nodes are isolated)")
    
    return True

def validate_neighbor_opinions(
    agent_id: str,
    opinions: object,
    config: dict,
) -> dict[str, str]:
    """
    Validate that neighbor_opinions only contains entries from adjacent agents.

    Args:
        agent_id: The receiving agent's ID.
        opinions:  The proposed neighbor_opinions dict.
        config:    Graph config dict with 'nodes' and 'edges'.

    Returns:
        Validated dict[str, str] of neighbor opinions.

    Raises:
        ValueError: If opinions contains non-adjacent or unknown agent IDs.
    """
    adjacency = build_adjacency_list(config["nodes"], config["edges"])
    allowed = set(adjacency.get(agent_id, []))

    if not isinstance(opinions, dict):
        raise ValueError("neighbor_opinions must be a dict.")
    invalid = sorted(k for k in opinions if k not in allowed)
    if invalid:
        raise ValueError(
            f"neighbor_opinions contains non-adjacent agents: {invalid}. "
            f"Allowed neighbors of '{agent_id}': {sorted(allowed)}"
        )
    blank = sorted(k for k, v in opinions.items() if not isinstance(v, str) or not v.strip())
    if blank:
        raise ValueError(f"neighbor_opinions has blank values for: {blank}")
    return dict(opinions)


def validate_graph_config_with_schema(config: dict, schema_path: str = "schemas/graph.schema.json") -> bool:
    """
    Validate graph config against the formal JSON Schema and connectivity.

    Args:
        config: Graph configuration dict.
        schema_path: Path to graph.schema.json relative to project root.

    Returns:
        True if valid, raises ValueError otherwise.
    """
    if jsonschema is not None:
        schema_file = PROJECT_ROOT / schema_path
        if schema_file.exists():
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
            try:
                jsonschema.validate(instance=config, schema=schema)
            except jsonschema.ValidationError as exc:
                raise ValueError(f"Graph config schema validation failed: {exc.message}") from exc

    # Also run existing Python-level validation
    return validate_graph_config(config)
