# Week 2 Intelligent Agent Framework: Comprehensive Merge & Architecture Guide

**Project Branch:** `Mariam` (Base Repository)  
**Location:** `/home/Herofis/projects/Qubettera_AI/M/Intelligent-Agent-Framework`  
**Generated Date:** 2026-09-05  

---

## 1. Executive Summary

This document explains the unified **Week 2 Intelligent Agent Framework** architecture resulting from merging three parallel implementations:
1. **Base Repository (`M/Intelligent-Agent-Framework`, branch `Mariam`)**: Provided the initial LangGraph scaffolding, Jinja2 templating, callback handler logging, multi-provider search foundation (DuckDuckGo, Tavily, Crawl4AI), and graph topology validation.
2. **Project Feature Repository (`project/Intelligent-Agent-Framework`)**: Provided direct pgvector Supabase retrieval via Kaggle Ollama embeddings, file-backed long-term memory (`AgentMemory`), rich persona configurations, the Python prompt builder with tool-availability gating, and an automated CLI runner.
3. **Hardened Architecture Repository (`N/Intelligent-Agent-Framework/week2-agent`, branch `Nada`)**: Provided the LangGraph checkpointer factory pattern, rolling context-window summarization (`manage_memory` node), durable PostgreSQL checkpointer, JSON Schema validation (Draft 2020-12), anti-prompt-injection defenses, structured retrieval output envelopes, and the single-function Week 3 handoff interface (`get_response`).

All 14 planned architectural changes have been successfully merged, tested, and verified. The complete automated test suite (29 tests) passes cleanly offline.

---

## 2. End-to-End Architecture Overview

```
                                 [ User / CLI / Handoff API ]
                                              │
                                              ▼
                             ┌──────────────────────────────────┐
                             │          get_response()          │
                             │  (Input Validation & Topology)   │
                             └────────────────┬─────────────────┘
                                              │
                                              ▼
                             ┌──────────────────────────────────┐
                             │       build_graph() Factory      │
                             │   (Durable or Memory Checkpoint) │
                             └────────────────┬─────────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 │
          ┌──────────────────────┐                                     │
   START ─►│    manage_memory     │                                     │
          └──────────┬───────────┘                                     │
                     │ (Keeps recent 5 exchanges;                      │
                     │  LLM summarizes older turns)                    │
                     ▼                                                 │
          ┌──────────────────────┐                                     │
   ┌─────►│      call_model      │ (Jinja2 System Prompt +             │
   │      └──────────┬───────────┘  Anti-Injection Defense)            │
   │                 │                                                 │
   │                 ├──────────────► [ No tool calls ] ──► END / Return
   │                 │ (Tool calls requested)                          │
   │                 ▼                                                 │
   │      ┌──────────────────────┐                                     │
   └──────│      tool_node       │                                     │
          └──────────┬───────────┘                                     │
                     │                                                 │
                     ├──► knowledge_retrieval (Direct Supabase + Kaggle Ollama)
                     ├──► live_web_search (Tavily REST / Keyless & DuckDuckGo)
                     └──► deep_web_crawl (Crawl4AI)
```

---

## 3. Detailed Component Breakdown

### 3.1. LLM Provider Layer (`src/llm/factory.py`)
- **Supported Providers**:
  - **Groq (`ChatGroq`)**: Fast inference, optimized for free-tier and open models (`openai/gpt-oss-20b`, `llama-3.3-70b-versatile`). Includes built-in rate-limit backoff parsing (`try again in X.Xs`).
  - **OpenRouter (`ChatOpenRouter`)**: Access to commercial and open models with retry handling.
  - **Ollama (`ChatOllama`)**: Local or tunnel-hosted models (`OLLAMA_BASE_URL`).
- **Callback Observability**: Attaches `AgentCallbackHandler` for local logging and optional Langfuse tracing (`LANGFUSE_ENABLED=true`).

### 3.2. Direct Knowledge Base Retrieval (`src/retrieval.py` & `src/tools/retrieval_tool.py`)
- **Elimination of FastAPI Middleman**: Replaces external HTTP microservice calls with direct, in-process database and embedding execution.
- **Embedding Pipeline**:
  - Direct connection to Ollama via `KAGGLE_OLLAMA_URL` (supporting both modern `client.embed()` and legacy `client.embeddings()` SDK APIs).
  - Defaults to `qwen3-embedding:8b`.
- **Database Query**:
  - Direct PostgreSQL connection (`psycopg2`) to Supabase (`DATABASE_URL`).
  - Cosine distance similarity search:
    ```sql
    SELECT chunk_id, document_id, text, metadata,
           embedding <=> %s::vector AS distance
    FROM chunks
    ORDER BY distance ASC
    LIMIT %s;
    ```
- **Output Contract**: Returns a structured JSON string containing `{"documents": [...], "error": ...}` with ranked chunks, source URLs, titles, and similarity metrics.

### 3.3. Two-Tier Agent Memory System
The framework combines two complementary memory mechanisms:
1. **Working & Windowed Memory (`src/agent/graph.py`)**:
   - `manage_memory` graph node checks total message history against `RECENT_EXCHANGES_TO_KEEP` (default 5).
   - If history exceeds the window, older messages are summarized by the LLM into `state["memory_summary"]`.
   - Protects the context window against token overflow during multi-turn debates.
   - If the summary LLM fails, the system falls back gracefully to full history without crashing.
2. **Durable & Cross-Session Memory**:
   - **Checkpointer (`src/agent/checkpoint.py`)**: Injected into `build_graph()`. Automatically selects `PostgresSaver` if PostgreSQL variables (`PGHOST`, `PGDATABASE`, etc.) are configured, otherwise cleanly defaults to `MemorySaver`.
   - **Persistent File Memory (`src/memory/agent_memory.py`)**: Append-only JSON persistence at `outputs/memory/<agent_id>.json`. Survives application restarts and records structured `MemoryEntry` items (`timestamp`, `kind`, `topic`, `content`).

### 3.4. Persona System & Schema Enforcement
- **Modular Storage**: Each persona resides in its own JSON file in `personas/` (e.g. `dr_aris.json`, `prof_elena.json`, `hybrid_architect.json`, `grad_student.json`, `moe_efficiency.json`, `dense_reliability.json`).
- **Formal Schema Validation (`personas/schema.json`)**: Enforces JSON Schema (Draft 2020-12) via `jsonschema`. Validates required fields (`name`, `background`, `stance`, `style`, `retrieval_focus`, `expertise`, `priorities`).
- **Cross-Repo Compatibility**: `src/personas/loader.py` dynamically normalizes field variations (e.g. `communication_style` $\leftrightarrow$ `style`, `persona_id` $\leftrightarrow$ `id`).

### 3.5. Topology & Neighbor Opinion Validation (`src/utils/graph_utils.py`)
- **Debate Graph Schema (`schemas/graph.schema.json`)**: Validates node definitions and undirected edges.
- **Anti-Spoofing Defense (`validate_neighbor_opinions`)**: Ensures an agent can only receive opinions from verified graph-adjacent neighbors. Rejects non-connected agent IDs before execution.

### 3.6. Prompt Engineering & Defenses (`prompts/system.jinja` & `prompts/opinion.jinja`)
- **Anti-Prompt-Injection Safeguards**: System prompt explicitly instructs the LLM that neighbor opinions and retrieved web content are *untrusted reference material* and to ignore embedded instructions.
- **Citation Integrity**: Demands verbatim source citations (`[Source: URL]`) and forbids claiming tool success on failures.
- **Dynamic Memory Block**: Renders `memory_summary` only when active, instructing the model to prioritize recent verbatim turns over the lossy summary.

### 3.7. Deterministic Opinion Pipeline (`src/pipelines/opinion.py`)
- Provides `generate_opinion(persona_id, topic)`:
  1. Loads validated persona.
  2. Constructs focused retrieval query (`persona.retrieval_focus + topic`).
  3. Executes retrieval tool; halts with `OpinionGenerationError` if evidence is empty or unreachable.
  4. Renders `opinion.jinja` prompt with evidence.
  5. Generates opinion via LLM.
  6. Enforces exact `[Source: URL]` citation validation.
  7. Persists output to `outputs/opinions/<timestamp>-<persona_id>.json`.
  8. Returns structured `OpinionResult`.

### 3.8. Week 3 Clean Handoff API (`src/handoff.py`)
- Provides a single entry point:
  ```python
  from src.handoff import get_response

  reply = get_response(
      agent_id="dr_aris",
      thread_id="round-1-dr-aris",
      user_message="Should we use MoE or Dense FFN?",
      neighbor_opinions={"prof_elena": "Dense layers are more predictable..."}
  )
  ```
- Handles checkpointer context, graph compilation, neighbor validation, and output extraction internally.

### 3.9. Web Tools & Search Providers (`src/web_search.py` & `src/search/tavily.py`)
- Upgraded Tavily integration to direct REST API calls.
- Supports **keyless access mode** (`X-Tavily-Access-Mode: keyless`) when `TAVILY_API_KEY` is not provided.
- Preserves DuckDuckGo (`ddgs`) and Crawl4AI providers.

---

## 4. File Structure of Merged Repository

```
M/Intelligent-Agent-Framework/
├── .env                              # Active environment configuration
├── .env.example                      # Template with all provider options
├── requirements.txt                  # Full dependency list
├── demo.py                           # Updated dual-agent demo with auto-save
├── cli.py                            # CLI runner supporting --topic, --personas
├── WEEK2_MERGE_EXPLANATION.md        # This comprehensive guide
│
├── personas/                         # Modular persona definitions & schema
│   ├── schema.json                   # Formal JSON Schema
│   ├── debate_graph.json             # Debate topology
│   ├── dr_aris.json                  # High-performance MoE advocate
│   ├── prof_elena.json               # Reliable Dense FFN advocate
│   ├── hybrid_architect.json         # Contextual hybrid systems expert
│   ├── grad_student.json             # Literature and novelty researcher
│   ├── moe_efficiency.json           # FLOP & throughput specialist
│   └── dense_reliability.json        # Production stability researcher
│
├── schemas/
│   └── graph.schema.json             # Formal topology schema
│
├── prompts/
│   ├── system.jinja                  # Hardened system prompt template
│   └── opinion.jinja                 # Grounded opinion template
│
├── src/
│   ├── __init__.py
│   ├── handoff.py                    # Week 3 public API (get_response)
│   ├── retrieval.py                  # Direct Supabase + Kaggle Ollama engine
│   ├── web_search.py                 # Direct Tavily REST client (keyless-capable)
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── checkpoint.py             # PostgresSaver / MemorySaver manager
│   │   ├── graph.py                  # build_graph() factory & manage_memory node
│   │   └── state.py                  # AgentState with windowing & document stores
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── factory.py                # Groq / OpenRouter / Ollama factory
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   └── agent_memory.py           # File-backed long-term memory
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── opinion.py                # OpinionResult dataclass & dedupe_sources
│   │
│   ├── personas/
│   │   ├── __init__.py
│   │   └── loader.py                 # Validated loader & schema validator
│   │
│   ├── pipelines/
│   │   ├── __init__.py
│   │   └── opinion.py                # Grounded opinion pipeline
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── builder.py                # Python prompt assembler with tool gating
│   │
│   ├── search/
│   │   ├── base.py                   # SearchProvider abstract base class
│   │   ├── crawl4ai.py               # Deep web crawler
│   │   ├── duckduckgo.py             # DuckDuckGo live search
│   │   ├── factory.py                # Search provider factory
│   │   └── tavily.py                 # REST Tavily provider
│   │
│   ├── tools/
│   │   ├── crawl_tool.py             # deep_web_crawl tool
│   │   ├── retrieval_tool.py         # knowledge_retrieval tool
│   │   └── search_tool.py            # live_web_search tool
│   │
│   └── utils/
│       ├── agent_utils.py            # Extraction utilities
│       ├── graph_utils.py            # Graph connectivity & neighbor validation
│       ├── langchain_callback.py     # Custom event logging handler
│       ├── logging_setup.py          # Formatted logging setup
│       └── prompt_loader.py          # Jinja2 template loader
│
├── outputs/
│   ├── opinions/                     # Persisted opinion JSON files
│   └── memory/                       # Per-agent persistent memory JSON files
│
└── tests/                            # Automated test suite (29 tests)
    ├── test_graph.py                 # State transitions & ReAct loops
    ├── test_handoff.py               # get_response API contract
    ├── test_memory.py                # File-backed AgentMemory isolation
    ├── test_memory_window.py         # Rolling summary window trimming
    ├── test_opinion.py               # Citation verification & error handling
    ├── test_personas.py              # Persona schema & distinctness tests
    ├── test_prompts.py               # Tool-availability prompt gating
    ├── test_retrieval.py             # Knowledge base mock tests
    └── test_web_search.py            # Keyless Tavily & rate-limit handling
```

---

## 5. Configuration Guide

To run with **Groq**:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=openai/gpt-oss-20b

DATABASE_URL=postgresql://postgres:...@...supabase.com:6543/postgres
KAGGLE_OLLAMA_URL=https://...ngrok-free.dev
EMBEDDING_MODEL=qwen3-embedding:8b

SEARCH_PROVIDER=duckduckgo
TAVILY_API_KEY=tvly-...
RECENT_EXCHANGES_TO_KEEP=5
```

---

## 6. Verification and Execution

### 6.1. Running the Automated Test Suite
All 29 unit tests run offline with mock services and require no live network connections:
```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

### 6.2. Running the Interactive CLI
```bash
source .venv/bin/activate

# Run with default personas (dr_aris, prof_elena)
python cli.py --topic "Should we use MoE or Dense Transformer architectures?"

# Run with all available personas
python cli.py --personas all --topic "Compare Sliding Window Attention vs Full Self-Attention"

# Run with specific personas and custom retrieval depth
python cli.py --personas dr_aris hybrid_architect --top-k 3
```

### 6.3. Running the Original Demo
```bash
source .venv/bin/activate
python demo.py
```
Output results are automatically saved to `outputs/opinions/`.

---

## 7. Conclusion

The merged framework achieves the objectives of Week 2:
- **Resilient**: Rolling memory summaries prevent context overflow; optional PostgreSQL checkpoints ensure debate state durability.
- **Decoupled & Fast**: Direct database and Kaggle Ollama access removes unnecessary microservice bottlenecks.
- **Defensive**: Formal JSON Schemas and anti-prompt-injection prompts protect against malformed configs and prompt hijacking.
- **Ready for Week 3**: The unified `get_response()` interface gives the upcoming multi-agent debate engine a clean, robust contract.
