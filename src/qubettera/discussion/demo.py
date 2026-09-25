"""Runnable Tasks 1-5 demonstration.

Examples:
    python -m qubettera.discussion.demo --mode fake
    python -m qubettera.discussion.demo --mode live
    python -m qubettera.discussion.demo --mode live --no-retrieval   # Task 1/2 only, NoRetrievalProvider
    python -m qubettera.discussion.demo --mode live --no-retrieval --no-agent-tools  # LLM-only turns
    python -m qubettera.discussion.demo --mode fake --topology ring
    python -m qubettera.discussion.demo --mode fake --topology full
    python -m qubettera.discussion.demo --mode fake --topology persona
    python -m qubettera.discussion.demo --mode live --parallel
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
from .console_stream import ConsoleTurnStream, resolve_persona_names
from .fakes import DeterministicAgentRuntime, DeterministicRetrievalProvider
from .interfaces import NoRetrievalProvider
from .orchestrator import DiscussionOrchestrator
from .output_naming import discussion_log_filename
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
    parser.add_argument(
        "--no-agent-tools",
        action="store_true",
        help="Live mode: compile the Week 2 graph with no tools (LLM-only turns).",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Execute agents concurrently within each round (~N× speedup for N agents).",
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

    if args.mode == "live":
        from .week2_adapter import Week2AgentRuntime

        runtime = Week2AgentRuntime(tools=[] if args.no_agent_tools else None)
    else:
        runtime = DeterministicAgentRuntime()

    if args.no_retrieval:
        retrieval_provider = NoRetrievalProvider()
    elif args.mode == "live":
        from .retrieval_provider import TeamRetrievalProvider

        retrieval_provider = TeamRetrievalProvider()
    else:
        retrieval_provider = DeterministicRetrievalProvider()

    graph = _build_graph(args, config.participant_ids)
    persona_names = resolve_persona_names(config.participant_ids)
    discussion_id = str(uuid4())
    output_filename = discussion_log_filename(
        mode=args.mode,
        num_agents=len(config.participant_ids),
        num_rounds=config.num_rounds,
        discussion_id=discussion_id,
        # The demo is the only entry point that can vary the topology, so it
        # carries that extra context in the prefix.
        prefix=f"demo-{args.topology}-",
    )
    output_path = Path(args.output_dir) / output_filename

    orchestrator = DiscussionOrchestrator(
        graph=graph,
        agent_runtime=runtime,
        retrieval_provider=retrieval_provider,
        event_sink=ConsoleTurnStream(JsonlEventSink(output_path), persona_names),
        id_factory=lambda: discussion_id,
        max_workers=len(config.participant_ids) if args.parallel else 1,
    )

    participants = ", ".join(
        f"{persona_names[agent_id]} ({agent_id})" for agent_id in config.participant_ids
    )
    print(f"\n{'=' * 60}")
    print(f"Objective: {config.brief.objective}")
    print(f"Participants: {participants}")
    print(f"Mode: {args.mode} | Topology: {args.topology} | Rounds: {config.num_rounds}")
    print(f"{'=' * 60}")
    print(f"\n{graph.render_ascii()}\n")

    result = orchestrator.run(config)
    discussion_turns = [message for message in result.messages if message.phase == "discussion"]
    retrieval_events = [
        message for message in result.messages if message.phase == "discussion" and message.retrieval_query
    ]

    print("\n" + "=" * 60)
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
