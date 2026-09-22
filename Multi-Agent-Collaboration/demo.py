#!/usr/bin/env python3
"""Week 2 — Agent Framework Demo (5 Personas).

Demonstrates five distinct agents debating and generating grounded opinions
on a Transformer architecture design task with external memory chaining.

Key features shown:
- Multi-agent debate across 5 diverse personas
- Dynamic tool-calling (ReAct loop) for internal & web retrieval
- External memory chaining (each agent receives neighbor opinions)
- Internal conversation memory recall (via thread_id persistence)
- Plug-and-play LLM (W&B Serverless Inference / Qwen)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# Load environment variables before importing components
load_dotenv(override=True)

from src import AgentState, graph
from src.utils import (
    extract_all_sources,
    extract_opinion,
    extract_tool_calls_trace,
    get_persona_by_id,
    load_personas,
    print_debug_info,
    serialize_message,
    setup_logging,
    stream_graph_with_trace,
)

# Configure root logger with file output
logger = setup_logging(
    console_level="INFO",
    file_level="DEBUG",
    log_dir="logs",
    log_prefix="agent_demo",
)




def run_demo():
    """Run the full agent demonstration."""

    logger.info("=" * 80)
    logger.info("Starting Week 2 Agent Demo")

    # 1. Load all personas
    personas = load_personas()
    print(f" Loaded {len(personas)} personas.")

    # 2. Select five diverse personas representing different architecture philosophies
    selected_ids = [
        "dr_aris",              # Pro-MoE / Inference Efficiency
        "prof_elena",           # Pro-Dense / Theoretical Rigor
        "hybrid_architect",     # Pragmatic Hybrid / Interleaved Layers
        "systems_specialist",   # Hardware & Kernels / GPU Bandwidth & Utilization
        "grad_student",         # Empirical Explorer / Latest 2025-2026 Trends
    ]
    selected_personas = [get_persona_by_id(personas, pid) for pid in selected_ids]

    # 3. Define the structured project task
    task = """
    Objective: Build a Transformer from scratch.
    Constraints: Hardware budget is one A100 GPU (40GB), timeline is 3 months.
    Topics to discuss:
        - MoE vs dense fully connected layers.
        - Should each layer be MoE, dense, or interleave (hybrid)?
        - Number of layers: 12 or 24?
        - Number of parameters: target ~1B.
        - Dimension space: 768 or 1024?
        - Latest advancements in research regarding transformer architecture such as the most recent papers (2025-2026)
    Strict Notes: You must search and retrieve grounded evidence using your retrieval tools before forming your recommendation. Evidence must always be cited with exact sources.
    """

    demo_start_time = time.time()
    accumulated_opinions: dict[str, str] = {}
    opinions_results: list[dict[str, Any]] = []
    detailed_agent_traces: list[dict[str, Any]] = []

    # --- Run opinion generation across the 5 personas independently ---
    for idx, persona in enumerate(selected_personas, 1):
        print("\n" + "=" * 80)
        print(f"PERSONA {idx}/5: {persona['name']} ({persona.get('id', '')})")
        print(f"Position: {persona.get('stance', 'N/A')}")
        print("=" * 80)

        initial_state: AgentState = {
            "task": task,
            "messages": [HumanMessage(content=task)],
            "neighbor_opinions": {},  # Independent opinion generation (no debate)
            "persona": persona,
            "final_opinion": "",
            "retrieved_docs": [],
            "web_documents": [],
            "retrieval_queries": [],
        }

        thread_id = f"demo_agent_{persona['id']}"
        config = {"configurable": {"thread_id": thread_id}}

        agent_start = time.time()
        logger.info("Invoking %s graph for independent opinion...", persona["name"])
        result = stream_graph_with_trace(graph, initial_state, config)
        opinion = extract_opinion(result)
        agent_elapsed = time.time() - agent_start
        print_debug_info(result)

        print(f"\n {persona['name']}'s OPINION:\n")
        print(opinion)
        print("\n" + "-" * 80)

        accumulated_opinions[persona["id"]] = opinion
        opinions_results.append({
            "agent_id": persona["id"],
            "persona_name": persona["name"],
            "opinion_text": opinion,
        })

        # Capture rich trace information
        agent_messages = result.get("messages", [])
        tool_calls = extract_tool_calls_trace(agent_messages)
        evidence_sources = extract_all_sources(agent_messages)

        detailed_agent_traces.append({
            "agent_id": persona["id"],
            "persona_name": persona["name"],
            "persona_config": dict(persona),
            "thread_id": thread_id,
            "elapsed_seconds": round(agent_elapsed, 2),
            "final_opinion": opinion,
            "summary_stats": {
                "opinion_length_chars": len(opinion),
                "tool_calls_count": len(tool_calls),
                "grounded_sources_count": len(evidence_sources),
                "retrieved_docs_count": len(result.get("retrieved_docs", [])),
                "web_documents_count": len(result.get("web_documents", [])),
                "retrieval_queries_count": len(result.get("retrieval_queries", [])),
            },
            "retrieval_queries": result.get("retrieval_queries", []),
            "retrieved_docs": result.get("retrieved_docs", []),
            "web_documents": result.get("web_documents", []),
            "grounded_sources": evidence_sources,
            "tool_calls": tool_calls,
            "execution_steps": result.get("step_trace", []),
            "memory_summary": result.get("memory_summary", ""),
            "messages_transcript": [serialize_message(m) for m in agent_messages],
        })
        time.sleep(1)

    # --- MEMORY TEST: Internal Memory ---
    print("\n" + "=" * 80)
    print("MEMORY TEST: Can Agent 1 (Dr. Aris) remember the previous conversation?")
    print("=" * 80)

    first_persona = selected_personas[0]
    config_first = {"configurable": {"thread_id": f"demo_agent_{first_persona['id']}"}}

    followup_state: AgentState = {
        "task": task,
        "messages": [HumanMessage(content="Can you summarize your previous opinion in one sentence?")],
        "neighbor_opinions": {},
        "persona": first_persona,
        "final_opinion": "",
        "retrieved_docs": [],
        "web_documents": [],
        "retrieval_queries": [],
    }

    followup_start = time.time()
    logger.info("Invoking %s with follow-up question (same thread_id)...", first_persona["name"])
    result_followup = stream_graph_with_trace(graph, followup_state, config_first)
    followup_response = extract_opinion(result_followup)
    followup_elapsed = time.time() - followup_start

    print(f"\nFollow-up Response from {first_persona['name']}:\n")
    print(followup_response)
    print("\n" + "-" * 80)

    followup_messages = result_followup.get("messages", [])
    followup_log = {
        "agent_id": first_persona["id"],
        "persona_name": first_persona["name"],
        "thread_id": config_first["configurable"]["thread_id"],
        "prompt": "Can you summarize your previous opinion in one sentence?",
        "response": followup_response,
        "elapsed_seconds": round(followup_elapsed, 2),
        "execution_steps": result_followup.get("step_trace", []),
        "messages_transcript": [serialize_message(m) for m in followup_messages],
    }

    total_elapsed = time.time() - demo_start_time

    # --- Summary ---
    print("\n" + "=" * 80)
    print("DEMO COMPLETE — All 5 personas generated independent technical opinions:")
    for p in selected_personas:
        print(f"  ✓ {p['name']} ({p['id']})")
    print("  - Independent grounded persona opinions (pure individual technical stances)")
    print("  - Dynamic tool-calling (grounding evidence retrieved via pgvector & search)")
    print("  - Internal thread memory (conversation history persisted via thread_id)")
    print("=" * 80)
    logger.info("Demo completed successfully for all 5 personas in %.2fs", total_elapsed)

    # --- Save JSON Files (Opinions Summary & Full Execution Log) ---
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    out_dir = Path("outputs/opinions")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / f"{timestamp_str}-demo.json"
    trace_path = out_dir / f"{timestamp_str}-trace.json"

    summary_payload = {
        "generated_at": timestamp_iso,
        "task": task.strip(),
        "trace_file": str(trace_path),
        "opinions": opinions_results,
        "followup": {
            "agent_id": first_persona["id"],
            "persona_name": first_persona["name"],
            "response": followup_response,
        },
    }

    full_log_payload = {
        "generated_at": timestamp_iso,
        "opinions_summary_file": str(summary_path),
        "task": task.strip(),
        "execution_metadata": {
            "total_elapsed_seconds": round(total_elapsed, 2),
            "llm_provider": os.getenv("LLM_PROVIDER", "unknown"),
            "llm_model": os.getenv("LLM_MODEL", "unknown"),
            "search_provider": os.getenv("SEARCH_PROVIDER", "duckduckgo"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "qwen3-embedding:8b"),
            "total_personas": len(selected_personas),
            "total_tool_calls": sum(a["summary_stats"]["tool_calls_count"] for a in detailed_agent_traces),
            "total_grounded_sources": sum(a["summary_stats"]["grounded_sources_count"] for a in detailed_agent_traces),
        },
        "personas": [
            {
                "id": p["id"],
                "name": p["name"],
                "stance": p.get("stance", ""),
            }
            for p in selected_personas
        ],
        "detailed_agent_traces": detailed_agent_traces,
        "followup_memory_test": followup_log,
    }

    summary_path.write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps(full_log_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"\n✓ Saved opinions summary to:     {summary_path}")
    print(f"✓ Saved comprehensive trace to: {trace_path}")

    return {
        "summary": summary_payload,
        "full_trace": full_log_payload,
        "summary_file": str(summary_path),
        "trace_file": str(trace_path),
        # Backward-compatible fields
        "generated_at": timestamp_iso,
        "task": task.strip(),
        "opinions": opinions_results,
        "followup": summary_payload["followup"],
    }


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    if not os.path.exists(".env"):
        print("WARNING: .env file not found. Please create one from .env.example")
        print("   Continuing with system defaults...")

    run_demo()

