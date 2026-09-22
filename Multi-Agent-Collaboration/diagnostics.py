#!/usr/bin/env python3
"""Intelligent Agent Framework — Interactive Diagnostics & Debug Suite.

Usage:
    python diagnostics.py              # Run all 6 component health checks
    python diagnostics.py --verbose    # Show detailed payloads, vectors, and traces
    python diagnostics.py --component llm        # Test only LLM
    python diagnostics.py --component retrieval  # Test only Kaggle Ollama + Supabase
    python diagnostics.py --component search     # Test only Web Search
    python diagnostics.py --component graph      # Test single agent graph run
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment before any framework imports
load_dotenv(override=True)


def _pass(msg: str) -> None:
    print(f"  \033[92m[PASS]\033[0m {msg}")


def _fail(msg: str, err: Any = None) -> None:
    print(f"  \033[91m[FAIL]\033[0m {msg}")
    if err:
        print(f"         \033[90mDetails: {err}\033[0m")


def _info(msg: str) -> None:
    print(f"  \033[94m[INFO]\033[0m {msg}")


def _warn(msg: str) -> None:
    print(f"  \033[93m[WARN]\033[0m {msg}")


def check_environment(verbose: bool = False) -> bool:
    print("\n" + "=" * 60)
    print(" 1. ENVIRONMENT & CONFIGURATION CHECK")
    print("=" * 60)

    env_path = Path(".env")
    if not env_path.exists():
        _fail(".env file not found! Copy from .env.example")
        return False
    _pass(f".env file detected at {env_path.resolve()}")

    provider = os.getenv("LLM_PROVIDER", "wandb").strip().lower()
    _info(f"Active LLM Provider: \033[1m{provider}\033[0m")

    if provider == "wandb":
        key = os.getenv("WANDB_API_KEY", "")
        model = os.getenv("LLM_MODEL") or os.getenv("WANDB_MODEL") or "Qwen/Qwen3.6-35B-A3B"
        if not key:
            _fail("WANDB_API_KEY is not set in .env")
            return False
        _pass(f"W&B API Key present ({key[:8]}...{key[-4:]})")
        _info(f"Target Model: {model}")
        _info(f"Base URL: {os.getenv('WANDB_BASE_URL', 'https://api.inference.wandb.ai/v1')}")
    elif provider == "groq":
        key = os.getenv("GROQ_API_KEY", "")
        model = os.getenv("GROQ_MODEL") or os.getenv("LLM_MODEL") or "qwen/qwen3.6-27b"
        if not key:
            _fail("GROQ_API_KEY is not set in .env")
            return False
        _pass(f"Groq API Key present ({key[:8]}...)")
        _info(f"Target Model: {model}")

    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        _pass("DATABASE_URL is set")
    else:
        _warn("DATABASE_URL is empty; retrieval will fall back to error envelopes")

    kaggle_url = os.getenv("KAGGLE_OLLAMA_URL", "")
    if kaggle_url:
        _pass(f"KAGGLE_OLLAMA_URL: {kaggle_url}")
    else:
        _warn("KAGGLE_OLLAMA_URL is empty; live embeddings will be unavailable")

    return True


def check_llm(verbose: bool = False) -> bool:
    print("\n" + "=" * 60)
    print(" 2. LLM CONNECTIVITY & TOOL CALLING CHECK")
    print("=" * 60)

    try:
        from src.llm.factory import get_chat_model
        from src.tools.retrieval_tool import knowledge_retrieval
        from langchain_core.messages import HumanMessage

        t0 = time.time()
        model = get_chat_model()
        _pass(f"Instantiated model: {model.__class__.__name__} ({getattr(model, 'model_name', 'default')})")

        # 1. Simple completion test
        _info("Sending test ping to LLM...")
        ping_res = model.invoke([HumanMessage(content="Reply with exactly: PING_OK")])
        latency = time.time() - t0
        content = ping_res.content.strip() if isinstance(ping_res.content, str) else str(ping_res.content)
        _pass(f"Ping successful in {latency:.2f}s: '{content[:60]}'")

        # 2. Tool-calling capability test
        _info("Testing tool-calling schema binding...")
        model_with_tools = model.bind_tools([knowledge_retrieval])
        tool_prompt = "Use knowledge_retrieval to search for 'MoE scaling laws'"
        tool_res = model_with_tools.invoke([HumanMessage(content=tool_prompt)])
        tool_calls = getattr(tool_res, "tool_calls", [])

        if tool_calls:
            tc = tool_calls[0]
            _pass(f"Tool-calling works! Agent generated tool call: {tc.get('name')}({tc.get('args')})")
        else:
            _warn("Model chose to answer directly instead of calling the tool.")
        return True

    except Exception as exc:
        _fail("LLM check failed", exc)
        return False


def check_kaggle_ollama(verbose: bool = False) -> bool:
    print("\n" + "=" * 60)
    print(" 3. KAGGLE OLLAMA EMBEDDING TUNNEL CHECK")
    print("=" * 60)

    kaggle_url = os.getenv("KAGGLE_OLLAMA_URL", "").strip()
    if not kaggle_url:
        _warn("KAGGLE_OLLAMA_URL not configured in .env; skipping.")
        return True

    try:
        import requests
        import ollama

        # 1. Check HTTP reachable
        _info(f"Pinging Kaggle tunnel: {kaggle_url}/api/tags ...")
        resp = requests.get(f"{kaggle_url}/api/tags", timeout=10)
        if resp.status_code != 200:
            _fail(f"Tunnel returned HTTP {resp.status_code}")
            return False
        models = [m.get("name") for m in resp.json().get("models", [])]
        _pass(f"Tunnel is alive! Available models on Kaggle: {models}")

        # 2. Generate embedding vector
        model_name = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:8b")
        _info(f"Generating test embedding with '{model_name}'...")
        client = ollama.Client(host=kaggle_url, timeout=30.0)
        t0 = time.time()
        res = client.embed(model=model_name, input="Test embedding for MoE Transformer architectures")
        embed_time = time.time() - t0

        embeddings = res.get("embeddings") if isinstance(res, dict) else getattr(res, "embeddings", None)
        if embeddings and len(embeddings) > 0:
            dim = len(embeddings[0])
            _pass(f"Successfully generated {dim}-dimension embedding vector in {embed_time:.2f}s!")
            if verbose:
                _info(f"Vector preview: {embeddings[0][:5]}...")
            return True
        else:
            _fail("Ollama response contained no embeddings.")
            return False

    except Exception as exc:
        _fail("Kaggle Ollama embedding check failed", exc)
        return False


def check_supabase_retrieval(verbose: bool = False) -> bool:
    print("\n" + "=" * 60)
    print(" 4. SUPABASE PGVECTOR RETRIEVAL CHECK")
    print("=" * 60)

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        _warn("DATABASE_URL not configured; skipping.")
        return True

    try:
        from src.retrieval import search_knowledge_base

        _info("Executing live search on Supabase pgvector knowledge base...")
        t0 = time.time()
        results = search_knowledge_base(query="MoE vs dense transformer architectures", top_k=2)
        elapsed = time.time() - t0

        _pass(f"Retrieved {len(results)} chunk(s) in {elapsed:.2f}s:")
        for r in results:
            title = r.get("title") or "Untitled"
            url = r.get("source_url") or "No URL"
            distance = r.get("distance", "N/A")
            dist_str = f"{distance:.4f}" if isinstance(distance, (int, float)) else str(distance)
            _info(f"  • Rank {r.get('rank')}: '{title}' (distance: {dist_str})")
            _info(f"    URL: {url}")
            if verbose:
                text_preview = (r.get("text") or "")[:200].replace("\n", " ")
                print(f"    Snippet: {text_preview}...")
        return True

    except Exception as exc:
        _fail("Supabase pgvector retrieval failed", exc)
        return False


def check_web_search(verbose: bool = False) -> bool:
    print("\n" + "=" * 60)
    print(" 5. LIVE WEB SEARCH CHECK")
    print("=" * 60)

    try:
        from src.tools.search_tool import live_web_search

        provider_name = os.getenv("SEARCH_PROVIDER", "duckduckgo")
        _info(f"Testing live web search provider ({provider_name})...")
        t0 = time.time()
        res = live_web_search.invoke({"query": "Transformer architecture research 2026"})
        elapsed = time.time() - t0

        if "Error" in res or not res.strip():
            _warn(f"Web search produced: {res[:200]}")
        else:
            _pass(f"Live web search succeeded in {elapsed:.2f}s!")
            lines = res.strip().splitlines()
            _info(f"Search results preview: {lines[0] if lines else 'OK'}")
        return True

    except Exception as exc:
        _fail("Live web search check failed", exc)
        return False


def check_graph_stream(verbose: bool = False) -> bool:
    print("\n" + "=" * 60)
    print(" 6. SINGLE-TURN AGENT GRAPH WITH STREAMING TRACE")
    print("=" * 60)

    try:
        from src.agent.graph import graph
        from src.personas.loader import load_persona
        from src.utils.debug_trace import stream_graph_with_trace
        from src.utils.agent_utils import extract_opinion
        from langchain_core.messages import HumanMessage

        persona = load_persona("dr_aris")
        task = "In 2 sentences, explain why MoE saves FLOPs compared to dense models."
        state = {
            "task": task,
            "messages": [HumanMessage(content=task)],
            "persona": dict(persona),
            "neighbor_opinions": {},
            "final_opinion": "",
            "retrieved_docs": [],
            "web_documents": [],
            "retrieval_queries": [],
        }
        config = {"configurable": {"thread_id": f"diagnostic-{int(time.time())}"}}

        _info("Starting real-time streaming execution...")
        result = stream_graph_with_trace(graph, state, config=config, verbose=verbose)
        opinion = extract_opinion(result)

        if opinion:
            _pass(f"Graph executed successfully! Generated {len(opinion)} character opinion.")
            print(f"\n\033[1m[Generated Opinion Preview]\033[0m\n{opinion}\n")
            return True
        else:
            _fail("Graph completed but returned empty opinion text.")
            return False

    except Exception as exc:
        _fail("Graph streaming check failed", exc)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run diagnostics and debug checks.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full debug payloads.")
    parser.add_argument(
        "--component",
        "-c",
        choices=["env", "llm", "ollama", "retrieval", "search", "graph", "all"],
        default="all",
        help="Run check for a specific component only.",
    )
    args = parser.parse_args()

    print("\n🔍 \033[1;36mINTELLIGENT AGENT FRAMEWORK — DIAGNOSTICS SUITE\033[0m")
    print("=" * 60)

    results: dict[str, bool] = {}

    if args.component in ("env", "all"):
        results["Environment"] = check_environment(args.verbose)
    if args.component in ("llm", "all"):
        results["LLM & Tool Calling"] = check_llm(args.verbose)
    if args.component in ("ollama", "all"):
        results["Kaggle Ollama"] = check_kaggle_ollama(args.verbose)
    if args.component in ("retrieval", "all"):
        results["Supabase Retrieval"] = check_supabase_retrieval(args.verbose)
    if args.component in ("search", "all"):
        results["Web Search"] = check_web_search(args.verbose)
    if args.component in ("graph", "all"):
        results["Graph Streaming"] = check_graph_stream(args.verbose)

    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    all_ok = True
    for name, ok in results.items():
        status = "\033[92mPASS\033[0m" if ok else "\033[91mFAIL\033[0m"
        print(f"  • {name:28} : {status}")
        if not ok:
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("\033[92mAll components are operational and ready for multi-agent execution!\033[0m\n")
        return 0
    else:
        print("\033[91mSome checks failed. See detailed output above to resolve issues.\033[0m\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

