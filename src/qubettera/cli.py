"""Unified Qubettera command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from qubettera.paths import CONFIGS_DIR, OUTPUTS_DIR


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qubettera")
    commands = parser.add_subparsers(dest="command", required=True)

    rag = commands.add_parser("rag")
    rag_commands = rag.add_subparsers(dest="rag_command", required=True)
    pipeline = rag_commands.add_parser("pipeline")
    pipeline.add_argument("--skip-collection", action="store_true")
    retrieve = rag_commands.add_parser("retrieve")
    retrieve.add_argument("query")
    retrieve.add_argument("--top-k", type=int, default=5)
    retrieve.add_argument("--adaptive-expand", action="store_true")
    retrieve.add_argument("--expansions", type=int, default=3)
    retrieve.add_argument("--json", action="store_true")
    evaluate = rag_commands.add_parser("evaluate")
    evaluate.add_argument("--require-complete-corpus", action="store_true")
    evaluate.add_argument(
        "--mode",
        choices=("all", "hybrid", "adaptive"),
        default="all",
    )

    agent = commands.add_parser("agent")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    opinion = agent_commands.add_parser("opinion")
    opinion.add_argument("persona_id")
    opinion.add_argument("topic")

    discuss = commands.add_parser("discuss")
    discuss_commands = discuss.add_subparsers(dest="discuss_command", required=True)
    run = discuss_commands.add_parser("run")
    run.add_argument("--mode", choices=("fake", "live"), default="fake")
    run.add_argument("--graph", default=str(CONFIGS_DIR / "agent_graph.json"))
    run.add_argument("--discussion", default=str(CONFIGS_DIR / "discussion.json"))
    run.add_argument("--output-dir", default=str(OUTPUTS_DIR / "discussions"))
    run.add_argument("--no-retrieval", action="store_true")

    commands.add_parser("doctor")
    return parser


def _run_pipeline(skip_collection: bool) -> None:
    if not skip_collection:
        from qubettera.rag.collection import run as collect

        collect()
    from qubettera.rag.chunk import run as chunk
    from qubettera.rag.clean import run as clean
    from qubettera.rag.embed import run as embed
    from qubettera.rag.store import run as store

    clean()
    chunk()
    embed()
    store()


def _run_discussion(args: argparse.Namespace) -> int:
    from uuid import uuid4

    from qubettera.discussion.agent_graph import AgentGraph
    from qubettera.discussion.config import load_discussion_config
    from qubettera.discussion.fakes import DeterministicAgentRuntime, DeterministicRetrievalProvider
    from qubettera.discussion.interfaces import NoRetrievalProvider
    from qubettera.discussion.orchestrator import DiscussionOrchestrator
    from qubettera.discussion.run_log import JsonlEventSink

    config = load_discussion_config(args.discussion)
    graph = AgentGraph.from_json(args.graph)
    discussion_id = str(uuid4())
    runtime = DeterministicAgentRuntime()
    retrieval_provider = DeterministicRetrievalProvider()
    if args.mode == "live":
        from qubettera.discussion.retrieval_provider import TeamRetrievalProvider
        from qubettera.discussion.week2_adapter import Week2AgentRuntime

        runtime = Week2AgentRuntime()
        retrieval_provider = TeamRetrievalProvider()
    if args.no_retrieval:
        retrieval_provider = NoRetrievalProvider()
    output = Path(args.output_dir) / f"{discussion_id}.jsonl"
    result = DiscussionOrchestrator(
        graph=graph,
        agent_runtime=runtime,
        retrieval_provider=retrieval_provider,
        event_sink=JsonlEventSink(output),
        id_factory=lambda: discussion_id,
    ).run(config)
    print(f"Discussion {result.discussion_id}: {result.status} ({len(result.messages)} messages)")
    print(f"Event log: {output}")
    return 0


def _doctor() -> int:
    from qubettera.agents.llm.factory import get_chat_model
    from qubettera.rag.retrieve import get_index_manifest

    failures = 0
    try:
        manifest = get_index_manifest()
        print(f"[OK] RAG index: {manifest['row_count']} chunks, {manifest['source_count']} sources")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] RAG database/index: {exc}")
    try:
        model = get_chat_model()
        print(f"[OK] Generation provider: {type(model).__name__}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Generation provider: {exc}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    args = _parser().parse_args(argv)
    if args.command == "doctor":
        return _doctor()
    if args.command == "rag" and args.rag_command == "pipeline":
        _run_pipeline(args.skip_collection)
        return 0
    if args.command == "rag" and args.rag_command == "retrieve":
        from qubettera.rag.retrieve import _console_safe, format_results, retrieve

        results = retrieve(
            args.query,
            top_k=args.top_k,
            expansion_count=args.expansions,
            adaptive_expand=args.adaptive_expand,
        )
        output = (
            json.dumps(results, indent=2, default=str, ensure_ascii=False)
            if args.json
            else format_results(results)
        )
        print(_console_safe(output))
        return 0
    if args.command == "rag" and args.rag_command == "evaluate":
        from qubettera.rag.evaluate import run_evaluation

        run_evaluation(
            allow_incomplete_corpus=not args.require_complete_corpus,
            mode=args.mode,
        )
        return 0
    if args.command == "agent" and args.agent_command == "opinion":
        from qubettera.agents.pipelines.opinion import generate_opinion

        result = generate_opinion(args.persona_id, args.topic)
        print(result["opinion_text"])
        return 0
    if args.command == "discuss" and args.discuss_command == "run":
        return _run_discussion(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())

