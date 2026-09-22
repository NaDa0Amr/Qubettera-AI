# Intelligent Agent Framework: Comprehensive System Guide

This document provides an end-to-end, technical explanation of the **Intelligent Agent Framework**—its architecture, execution lifecycle, inference engine, retrieval grounding, persona isolation, trace logging schema, and multi-agent debate dynamics.

---

## 1. System Mission & Task Context

The Intelligent Agent Framework is an agentic AI system designed to simulate high-stakes technical architecture debates among specialized expert personas. 

### The Core Architecture Challenge
The personas are tasked with designing a **1B parameter Transformer model** optimized for high reasoning and inference throughput under strict production constraints:
* **Hardware Budget:** Exactly **one NVIDIA A100 GPU (40GB VRAM)**.
* **Timeline:** **3 months** from design to deployment.
* **Core Decisions:**
  1. **Dense vs. Sparse Mixture of Experts (MoE)**
  2. **Hybrid Architecture (SSM / Mamba / Sliding Window) vs. Pure Transformer**
  3. **Depth (12 vs. 24 vs. 32 layers)**
  4. **Hidden Dimension Space (768 vs. 1024 vs. 2048)**

Every recommendation must be **grounded in empirical research evidence** retrieved from internal vector stores and live web search, accompanied by verbatim citations.

---

## 2. End-to-End System Architecture

The core of each agent is a compiled **LangGraph `StateGraph`** operating with an injected checkpointer and an automated ReAct tool loop.

```
                     ┌─────────────────────────┐
                     │          START          │
                     └────────────┬────────────┘
                                  │
                                  ▼
                     ┌─────────────────────────┐
                     │      manage_memory      │◄── (Summarizes older turns if
                     └────────────┬────────────┘     history > RECENT_EXCHANGES)
                                  │
                                  ▼
                     ┌─────────────────────────┐
                     │       call_model        │◄──────────┐
                     └────────────┬────────────┘           │
                                  │                        │
                      [Tool Calls Proposed?]               │
                         /              \                  │
                      YES                NO                │
                       /                  \               │
                      ▼                    ▼               │
           ┌──────────────────────┐   ┌─────────┐          │
           │      tool_node       │   │   END   │          │
           │ (pgvector, web, etc.)│   └─────────┘          │
           └──────────┬───────────┘                        │
                      │                                    │
                      └────────────────────────────────────┘
```

### The Node Execution Lifecycle
1. **`manage_memory`**:
   - Inspects the message history before invoking the LLM.
   - Keeps the last $N$ human exchanges verbatim (default: 5).
   - If the conversation exceeds the window, an LLM summarizer condenses older messages into `memory_summary`, preventing context-window overflow while preserving technical constraints.
2. **`call_model`**:
   - Renders the persona prompt via Jinja2 (`prompts/system.jinja`).
   - Injects the persona background, stance, priorities, retrieval focus, untrusted neighbor opinions (with prompt-injection defense), and memory summary.
   - Invokes the tool-bound chat model.
   - On the initial research turn, if the model attempts to answer without calling tools on an empirical architecture task, it is nudged once to execute a retrieval tool.
3. **`tool_node`**:
   - Concurrently executes requested tools (`knowledge_retrieval`, `live_web_search`, `deep_web_crawl`).
   - Enforces a safety throttle of **maximum 5 web searches per run**.
   - Accumulates structured results into `state["retrieved_docs"]`, `state["web_documents"]`, and `state["retrieval_queries"]`.
   - Returns control back to `call_model` to synthesize the grounded recommendation.

---

## 3. Inference Engine & LLM Provider

### Weights & Biases (W&B) Serverless Inference
The framework is configured to use W&B inference:
* **Provider:** `wandb`
* **Base URL:** `https://api.inference.wandb.ai/v1`
* **Model:** `Qwen/Qwen3.6-35B-A3B`
  - MoE architecture with **3B active parameters** and **35B total parameters**.
  - **262k context window**, ideal for multi-document technical reasoning.
* **Reasoning Optimization (`reasoning_effort="none"`):**
  - To prevent thinking token loops from stalling tool execution and hitting timeouts, `src/llm/factory.py` sets `reasoning_effort="none"` directly in `ChatOpenAI`.
  - This eliminates verbose thinking token overhead while preserving 100% structured tool-calling accuracy and instant synthesis.

### Multi-Provider Architecture
The factory (`src/llm/factory.py`) also supports:
* **Groq:** `llama-3.3-70b-versatile` or `openai/gpt-oss-20b` with automated rate-limit backoff parsing.
* **OpenRouter:** `ChatOpenRouter` with commercial or open-source endpoints.
* **Ollama:** Local or tunneled models (e.g. `gemma3:4b`).

---

## 4. Evidence Grounding & Retrieval Subsystem

### A. Internal Knowledge Base (Supabase pgvector)
* **Storage:** Supabase PostgreSQL database containing chunked research papers on Transformers, MoE, State Space Models, and attention mechanisms.
* **Embedding Model:** `qwen3-embedding:8b` hosted via Kaggle Ollama ngrok tunnel.
* **Vector Operator:** In-process cosine distance search (`<=>` operator) via `src/retrieval.py`.
* **Tool Interface:** `knowledge_retrieval(query: str, top_k: int = 5)`.

### B. Automatic LLM Query Reformulation
When retrieval yields weak or empty results, the system does not fail silently:
1. If results are empty OR the top result has poor relevance (**`distance > 0.40`**), `_regenerate_query_with_llm()` is triggered.
2. The LLM acts as a retrieval engineer, rewriting verbose or conversational queries into 6–12 dense technical keywords (e.g. focusing on routing, MFU, or memory bandwidth).
3. Retrieval is retried with the regenerated query. If the retry improves cosine distance, it replaces the original results and records `"query_regenerated": true`.

### C. Live Web Search & Crawling
* **Provider:** DuckDuckGo (via `ddgs`) with fallback to Tavily REST API (supporting keyless mode).
* **Search Limit:** Capped at **5 searches per agent run** (`MAX_WEB_SEARCHES_PER_RUN = 5`) to prevent rate-limit exhaustion.
* **Deep Crawl:** `deep_web_crawl` uses Crawl4AI to pull full markdown content from specific identified URLs.

### D. Untruncated Text Logging
* Legacy character clamps (`[:600] + "... (truncated)"`) have been removed.
* 100% of chunk text is preserved in `AgentState["retrieved_docs"]` and written directly into output JSON files.

---

## 5. The 5 Expert Personas & The 1B Model Debate

Every persona is loaded from an isolated configuration file (`personas/*.json`) validated against `personas/schema.json`:

```
                               THE 5 EXPERT PERSONAS

  1. Dr. Aris Thorne            2. Prof. Elena Vance           3. Dr. Samira Chen
     [Pragmatic MoE]               [Academic Skeptic]             [Hybrid Architect]
     • Sparse MoE (Top-2)          • Pure Dense FFN               • Interleaved Dense + MoE
     • Sliding Window Attn         • Full Global Attention        • Sliding Window Attn
     • 24 Layers, d=768            • 24 Layers, d=1024            • 24 Layers, d=1024
     • Focus: SSM & MoE Scaling    • Focus: Routing Failures      • Focus: Production Trade-offs
              │                             │                              │
              └─────────────────────────────┼──────────────────────────────┘
                                            │
                      ┌─────────────────────┴──────────────────────┐
                      │                                            │
            4. Systems Specialist                        5. Leo Kowalski
               [CUDA & Kernels]                             [PhD Student]
               • Pure Dense GEMMs                           • MoE + Mamba-2 SSM
               • FlashAttention-2                           • Linear Attention
               • 24 Layers, d=1024                          • 24 Layers, d=1024
               • Focus: MFU & DRAM Bandwidth                • Focus: SOTA 2025/2026 Papers
```

### Persona Independence & State Isolation
* **Separate Threads:** Each agent runs under its own checkpointer thread (`demo_agent_dr_aris`, `demo_agent_prof_elena`, etc.).
* **Zero Cross-Contamination:** Each persona starts with an empty document store (`retrieved_docs: []`, `web_documents: []`).
* **Persona-Driven Queries:** Each agent formulates queries strictly from its own `retrieval_focus`.
  - Elena searched for routing instability and load-balancing failures.
  - The Systems Specialist searched for CUDA kernel memory access and FLOP-to-byte ratios.
  - Dr. Aris searched for SSM efficiency and sliding window benchmarks.

### The Technical Debate: Consensus vs. Conflict
* **The Unanimous Consensus (Depth = 24 Layers):**
  All 5 personas independently converged on **24 layers**.
  - 12 layers lacks expressivity for multi-hop reasoning.
  - 32 layers is too deep to train on a single A100 in 3 months.
* **The Central Conflict (MoE vs. Dense):**
  - **Algorithmic Stance (Aris & Leo):** MoE expands total capacity (1B) while keeping active compute low (~250M-300M tokens), maximizing expressivity.
  - **Hardware Stance (Systems Specialist & Elena):** On a *single GPU*, dynamic MoE routing causes uncoalesced memory reads and kernel launch latency, dropping Model FLOPs Utilization (MFU) below 35%. Pure Dense GEMMs with FlashAttention-2 achieve >70% peak MFU, making it the only reliable choice for a 3-month deadline.
  - **Synthesizer Stance (Samira):** Hybrid model with Dense lower layers (semantic stability) and Sparse MoE upper layers (specialized reasoning).

---

## 6. Trace Logging & Deduplicated Schema

The framework outputs two companion files under `outputs/opinions/`:
1. **`<timestamp>-demo.json`**: High-level summary of the 5 opinions and follow-up memory test.
2. **`<timestamp>-trace.json`**: Comprehensive, deduplicated audit log.

### The Clean Deduplicated Schema
Previously, document texts were duplicated up to 4 times across different keys (causing 670 KB+ files). The schema has been refactored to establish a **single source of truth**:

```json
{
  "generated_at": "2026-09-06T12:46:06Z",
  "execution_metadata": {
    "total_elapsed_seconds": 195.91,
    "llm_provider": "wandb",
    "llm_model": "Qwen/Qwen3.6-35B-A3B",
    "total_personas": 5,
    "total_tool_calls": 17,
    "total_grounded_sources": 76
  },
  "detailed_agent_traces": [
    {
      "agent_id": "dr_aris",
      "persona_name": "Dr. Aris Thorne",
      "thread_id": "demo_agent_dr_aris",
      "elapsed_seconds": 45.61,
      "final_opinion": "...",
      "summary_stats": {
        "opinion_length_chars": 7176,
        "tool_calls_count": 5,
        "retrieved_docs_count": 10,
        "web_documents_count": 20,
        "grounded_sources_count": 24,
        "retrieval_queries_count": 1
      },
      "persona_config": { ... },
      "retrieval_queries": [ ... ],

      "retrieved_docs": [
        {
          "rank": 1,
          "title": "Mamba",
          "url": "https://arxiv.org/pdf/2312.00752.pdf",
          "distance": 0.2854,
          "score": 0.2854,
          "text": "FULL UNTRUNCATED CHUNK TEXT FROM PGVECTOR..."
        }
      ],

      "web_documents": [
        {
          "title": "...",
          "url": "...",
          "snippet": "...",
          "text": "FULL UNTRUNCATED WEB SEARCH TEXT..."
        }
      ],

      "grounded_sources": [
        {
          "tool": "knowledge_retrieval",
          "title": "Mamba",
          "url": "https://arxiv.org/pdf/2312.00752.pdf",
          "distance": 0.2854,
          "rank": 1,
          "snippet": "Concise preview (no full text duplicated here)..."
        }
      ],

      "tool_calls": [
        {
          "call_index": 1,
          "tool_name": "knowledge_retrieval",
          "arguments": { "query": "...", "top_k": 5 },
          "status": "OK",
          "documents_returned": 5,
          "summary": "Successfully returned 5 grounded document(s)"
        }
      ],

      "execution_steps": [ ... ],

      "messages_transcript": [
        { "role": "human", "content": "Task description..." },
        { "role": "ai", "tool_calls": [ ... ] },
        { "role": "tool", "content": "[knowledge_retrieval returned 5 grounded document(s) -> stored in retrieved_docs]" },
        { "role": "ai", "content": "### 1. Final Recommendation..." }
      ]
    }
  ],
  "followup_memory_test": { ... }
}
```

* **Storage Efficiency:** File size reduced by **>55%** (from 671 KB to ~302 KB).
* **Readability:** Clean separation between canonical text storage (`retrieved_docs`, `web_documents`), citation bibliography (`grounded_sources`), tool status (`tool_calls`), and conversational flow (`messages_transcript`).

---

## 7. Memory Persistence & Follow-Up Test

The framework supports three levels of memory:
1. **Thread Checkpointer (`get_checkpointer()`):**
   - Retains conversation state per `thread_id` across turns.
   - Tested in `demo.py`: Dr. Aris Thorne is asked to summarize his opinion in one sentence.
   - **Response Time:** **1.25s** (bypasses tool calls, synthesizes directly from state).
   - **Result:** Accurately synthesized the exact 24-layer, MoE, and sliding window specifications from his previous turn.
2. **Context Summarization (`manage_memory`):**
   - Automatically compresses older turns into `memory_summary` when conversation history grows.
3. **File-Backed Persistence (`AgentMemory`):**
   - Writes append-only logs to `outputs/memory/<agent_id>.json`, surviving full process restarts.

---

## 8. Multi-Agent Handoff Interface (Week 3 Preparation)

For Week 3 multi-agent debate and graph orchestration, the framework exposes a single entry point:

```python
from src.handoff import get_response

response_text = get_response(
    agent_id="dr_aris",
    thread_id="debate_round_1",
    user_message="Critique Prof. Elena Vance stance on dense layers.",
    neighbor_opinions={
        "prof_elena": "Dense layers are required for training stability on a single A100..."
    }
)
```

* **Adjacency Validation:** `validate_neighbor_opinions()` verifies that `neighbor_opinions` only accepts input from permitted adjacent agents defined in `debate_graph.json` according to `schemas/graph.schema.json`.

---

## 9. Verification & Commands

### Running the Test Suite
All 40 unit and integration tests run offline without network dependencies:
```bash
source .venv/bin/activate
pytest -v
```
**Status:** `40 passed in 1.78s`.

### Running the 5-Persona Demo
```bash
source .venv/bin/activate
python demo.py
```

### Running the Interactive CLI
```bash
source .venv/bin/activate
python cli.py --topic "MoE vs Dense on A100" --personas dr_aris prof_elena
```

### Inspecting Output JSON Files
```bash
# View opinion summaries
cat outputs/opinions/*-demo.json | jq .opinions[].persona_name

# View execution metadata
cat outputs/opinions/*-trace.json | jq .execution_metadata

# Inspect full untruncated chunk text
cat outputs/opinions/*-trace.json | jq .detailed_agent_traces[0].retrieved_docs[0].text
```
