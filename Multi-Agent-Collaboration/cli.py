#!/usr/bin/env python3
"""CLI runner for Week 2 agent demos.

Usage:
    python cli.py                                   # default topic, dr_aris + prof_elena
    python cli.py --topic "SSM vs Transformer"
    python cli.py --personas dr_aris prof_elena hybrid_architect
    python cli.py --personas all                   # all available personas
    python cli.py --top-k 3
    python cli.py --skip-memory-demo
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Load environment variables before initializing components
load_dotenv(override=True)

from src.agent.checkpoint import get_checkpointer
from src.agent.graph import build_graph
from src.memory import AgentMemory
from src.personas.loader import PersonaConfig, PersonaConfigError, load_all_personas, load_persona
from src.utils.agent_utils import extract_opinion

DEFAULT_TOPIC = "What are the trade-offs between MoE and Dense Transformer architectures for large-scale LLM training?"
DEFAULT_PERSONAS = ["dr_aris", "prof_elena"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Week 2 agent framework demo.")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="Discussion topic.")
    parser.add_argument(
        "--personas",
        nargs="+",
        default=DEFAULT_PERSONAS,
        help="Persona IDs to run, or 'all' for every persona in personas/.",
    )
    parser.add_argument("--top-k", type=int, default=5, dest="top_k", help="Retrieval depth.")
    parser.add_argument("--skip-memory-demo", action="store_true", help="Skip the memory test step.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # Resolve personas
    if args.personas == ["all"] or "all" in args.personas:
        personas = list(load_all_personas().values())
    else:
        personas = []
        for pid in args.personas:
            try:
                personas.append(load_persona(pid))
            except PersonaConfigError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2

    if not personas:
        print("ERROR: No personas loaded.", file=sys.stderr)
        return 2

    print(f"\n{'='*60}")
    print(f"Topic: {args.topic}")
    print(f"Personas: {[p.name for p in personas]}")
    print(f"{'='*60}\n")

    results: list[dict[str, Any]] = []
    with get_checkpointer() as checkpointer:
        for persona in personas:
            print(f"\n--- {persona.name} ---")
            g = build_graph(checkpointer=checkpointer)
            graph_input = {
                "task": args.topic,
                "messages": [HumanMessage(content=args.topic)],
                "persona": dict(persona),
                "neighbor_opinions": {},
                "final_opinion": "",
                "retrieved_docs": [],
                "web_documents": [],
                "retrieval_queries": [],
            }
            config = {"configurable": {"thread_id": f"cli-{persona.id}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"}}
            result = g.invoke(graph_input, config=config)
            opinion = extract_opinion(result)
            print(opinion[:500] + "..." if len(opinion) > 500 else opinion)

            AgentMemory(persona.id).add(kind="opinion", topic=args.topic, content=opinion)

            results.append({
                "agent_id": persona.id,
                "persona_name": persona.name,
                "topic": args.topic,
                "opinion_text": opinion,
            })

            # Optional memory demo for the first persona
            if not args.skip_memory_demo and persona == personas[0]:
                print(f"\n[Memory Test] Verifying thread memory recall for {persona.name}...")
                followup_input = {
                    "task": args.topic,
                    "messages": [HumanMessage(content="Can you summarize your previous opinion in one sentence?")],
                    "persona": dict(persona),
                    "neighbor_opinions": {},
                    "final_opinion": "",
                    "retrieved_docs": [],
                    "web_documents": [],
                    "retrieval_queries": [],
                }
                followup_result = g.invoke(followup_input, config=config)
                followup_opinion = extract_opinion(followup_result)
                print(f"[Memory Test Response]: {followup_opinion[:300]}...")

    # Save output
    out_dir = Path("outputs/opinions")
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-cli.json"
    out_path = out_dir / filename
    out_path.write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "topic": args.topic, "opinions": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
