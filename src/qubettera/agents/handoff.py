"""Single Week 3 entry point — hides graph and checkpointer internals.

Ported from N/week2-agent/src/handoff.py.

Usage (Week 3 orchestrator):
    from qubettera.agents.handoff import get_response

    reply = get_response(
        agent_id="dr_aris",
        thread_id="debate-round-1-dr-aris",
        user_message="What is your stance on MoE?",
        neighbor_opinions={"prof_elena": "Dense layers are more reliable..."},
    )
"""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage

from qubettera.agents.agent.checkpoint import get_checkpointer, open_postgres_checkpointer
from qubettera.agents.agent.graph import build_graph
from qubettera.agents.personas.loader import load_persona
from qubettera.discussion.agent_graph import AgentGraph
from qubettera.paths import CONFIGS_DIR


def get_response(
    agent_id: str,
    thread_id: str,
    user_message: str,
    *,
    neighbor_opinions: dict[str, str] | None = None,
    topology_path: str | None = None,
) -> str:
    """Invoke one agent and return its text response.

    Args:
        agent_id:          Persona ID (e.g. 'dr_aris').
        thread_id:         Unique thread identifier for LangGraph memory.
        user_message:      The human turn to send to the agent.
        neighbor_opinions: Optional dict of adjacent agent ID -> opinion text.
        topology_path:     Optional path to debate_graph.json (for validation).

    Returns:
        Plain string response from the agent.

    Raises:
        ValueError: On invalid inputs or non-adjacent neighbor opinions.
        RuntimeError: If the graph ends without an assistant response.
    """
    if not isinstance(thread_id, str) or not thread_id.strip() or len(thread_id) > 255:
        raise ValueError("thread_id must be a non-blank string of 1 to 255 characters.")
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("user_message must not be blank.")

    neighbors: dict[str, str] = {}
    if neighbor_opinions is not None:
        topology = AgentGraph.from_json(topology_path or CONFIGS_DIR / "agent_graph.json")
        if not isinstance(neighbor_opinions, dict):
            raise ValueError("neighbor_opinions must be a dict.")
        allowed = set(topology.senders(agent_id))
        if set(neighbor_opinions) - allowed:
            raise ValueError("neighbor_opinions contains non-adjacent agents.")
        if any(not isinstance(value, str) or not value.strip() for value in neighbor_opinions.values()):
            raise ValueError("neighbor_opinions has blank values.")
        neighbors = dict(neighbor_opinions)

    persona = load_persona(agent_id)
    graph_input = {
        "task": user_message,
        "neighbor_opinions": neighbors,
        "final_opinion": "",
        "messages": [HumanMessage(content=user_message)],
        "persona": dict(persona),
        "retrieved_docs": [],
        "web_documents": [],
        "retrieval_queries": [],
    }
    config_dict = {"configurable": {"thread_id": thread_id}}

    with get_checkpointer() as checkpointer:
        result = build_graph(checkpointer=checkpointer).invoke(graph_input, config=config_dict)

    final_message = (result.get("messages") or [None])[-1]
    if not isinstance(final_message, AIMessage):
        raise RuntimeError("Graph ended without an assistant response.")
    content = final_message.content
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)
