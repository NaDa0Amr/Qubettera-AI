"""Runnable Tasks 1-5 demonstration.

Examples:
    python -m week3.demo --mode fake
    python -m week3.demo --mode live
    python -m week3.demo --mode live --no-retrieval   # Task 1/2 only, NoRetrievalProvider
    python -m week3.demo --mode fake --topology ring
    python -m week3.demo --mode fake --topology full
    python -m week3.demo --mode fake --topology persona
"""

from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

# Load .env before anything below (retrieval_provider, week2_adapter -> src.llm.factory)
# reads LLM/DB/embedding env vars, mirroring cli.py and the root demo.py.
load_dotenv(override=True)

from .agent_graph import AgentGraph
from .config import load_discussion_config
from .fakes import DeterministicAgentRuntime, DeterministicRetrievalProvider
from .interfaces import NoRetrievalProvider
from .orchestrator import DiscussionOrchestrator
from .run_log import JsonlEventSink

from qubettera.agents.graph_builder import GraphBuilder
from qubettera.paths import CONFIGS_DIR, OUTPUTS_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Week 3 Tasks 1-5 demonstration.")
    parser.add_argument("--mode", choices=("fake", "live"), default="fake")
    parser.add_argument("--graph", default=str(CONFIGS_DIR / "agent_graph.json"))
    parser.add_argument("--discussion", default=str(CONFIGS_DIR / "discussion.json"))
    parser.add_argument("--output-dir", default=str(OUTPUTS_DIR / "discussions"))
    parser.add_argument(
        "--topology",
        choices=("json", "ring", "full", "star", "persona"),
        default="json",
        help="Graph generation strategy. 'json' loads from --graph file (default).",
    )
    parser.add_argument(
        "--no-retrieval",
        action="store_true",
        help="Disable Task 5 retrieval and fall back to NoRetrievalProvider.",
    )
    return parser.parse_args()


def _build_graph(args: argparse.Namespace, participant_ids: tuple[str, ...]) -> AgentGraph:
    """Build the agent graph using the chosen topology strategy."""
    ids = list(participant_ids)
    if args.topology == "json":
        return AgentGraph.from_json(args.graph)
    elif args.topology == "ring":
        return GraphBuilder.ring(ids)
    elif args.topology == "full":
        return GraphBuilder.fully_connected(ids)
    elif args.topology == "star":
        return GraphBuilder.star(hub=ids[0], spokes=ids[1:])
    elif args.topology == "persona":
        return GraphBuilder.from_persona_ids(ids)
    raise ValueError(f"Unknown topology: {args.topology!r}")


def main() -> int:
    args = parse_args()
    config = load_discussion_config(args.discussion)
    graph = _build_graph(args, config.participant_ids)
    discussion_id = str(uuid4())
    output_path = Path(args.output_dir) / f"{discussion_id}.jsonl"

    if args.mode == "live":
        from .week2_adapter import Week2AgentRuntime

        runtime = Week2AgentRuntime()
    else:
        runtime = DeterministicAgentRuntime()

    if args.no_retrieval:
        retrieval_provider = NoRetrievalProvider()
    elif args.mode == "live":
        from .retrieval_provider import TeamRetrievalProvider

        retrieval_provider = TeamRetrievalProvider()
    else:
        retrieval_provider = DeterministicRetrievalProvider()

    orchestrator = DiscussionOrchestrator(
        graph=graph,
        agent_runtime=runtime,
        retrieval_provider=retrieval_provider,
        event_sink=JsonlEventSink(output_path),
        id_factory=lambda: discussion_id,
    )
    result = orchestrator.run(config)
    discussion_turns = [message for message in result.messages if message.phase == "discussion"]
    retrieval_events = [
        message for message in result.messages if message.phase == "discussion" and message.retrieval_query
    ]

    print(f"\n{graph.render_ascii()}\n")
    print(f"Discussion ID: {result.discussion_id}")
    print(f"Status: {result.status}")
    print(f"Topology: {args.topology}")
    print(f"Directed graph strongly connected: {graph.is_strongly_connected()}")
    print(f"Participants: {len(config.participant_ids)}")
    print(f"Discussion rounds: {config.num_rounds}")
    print(f"Initial opinions: {len(config.participant_ids)}")
    print(f"Discussion turns: {len(discussion_turns)}")
    print(f"Discussion-round retrieval events: {len(retrieval_events)}")
    print(f"Event log: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
