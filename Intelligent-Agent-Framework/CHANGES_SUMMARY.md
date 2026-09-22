# Intelligent Agent Framework: Summary of Changes & Upgrades

**Repository:** `M/Intelligent-Agent-Framework`  
**Target Branch:** `Mariam`  
**Latest Update:** 2026-09-06  
**Verification:** **40/40 Pytest Suites Passing**  

---

## 1. File Modification & Addition Matrix

| File Path | Status | Core Change / Purpose |
|:---|:---:|:---|
| `requirements.txt` | **MODIFIED** | Added `langchain-groq`, `langchain-openrouter`, `langchain-openai`, `psycopg2-binary`, `ollama`, `jsonschema`, `langgraph-checkpoint-postgres` |
| `.env.example` | **MODIFIED** | Added configurations for W&B (`wandb`), Groq, Supabase `DATABASE_URL`, Kaggle `KAGGLE_OLLAMA_URL`, and Postgres |
| `.env` | **NEW** | Configured active W&B serverless inference credentials, `Qwen/Qwen3.6-35B-A3B`, Supabase URL, and Kaggle Ollama tunnel |
| `src/llm/factory.py` | **MODIFIED** | Integrated **Weights & Biases (`wandb`)** serverless inference (`ChatOpenAI` pointing to `https://api.inference.wandb.ai/v1`); added `reasoning_effort="none"` for Qwen to eliminate thinking token stalls; preserved Groq, OpenRouter, and Ollama |
| `src/retrieval.py` | **NEW** | Direct Supabase (pgvector) + Kaggle Ollama embedding client (`qwen3-embedding:8b`) with cosine similarity (`<=>`), bypassing external FastAPI services |
| `src/tools/retrieval_tool.py` | **MODIFIED** | Added **automatic LLM query reformulation** (`_regenerate_query_with_llm`) when chunks are empty or distance > 0.40; removed text truncation clamps to preserve 100% full chunk text |
| `src/search/base.py` | **MODIFIED** | Upgraded `SearchResult.to_markdown()` to preserve full text without character truncation |
| `src/agent/state.py` | **MODIFIED** | Extended `AgentState` with `memory_summary`, `summarized_message_count`, `retrieved_docs`, `web_documents`, and `retrieval_queries` |
| `src/agent/graph.py` | **MODIFIED** | Converted to `build_graph()` factory with injectable checkpointer; added `manage_memory` rolling summary node; enforced `MAX_WEB_SEARCHES_PER_RUN = 5` cap; added mandatory retrieval on initial research turns |
| `src/agent/checkpoint.py` | **NEW** | Added `open_postgres_checkpointer()` and `get_checkpointer()` with automatic fallback to `MemorySaver` |
| `src/memory/agent_memory.py` | **NEW** | File-backed append-only persistent memory (`outputs/memory/<agent_id>.json`) surviving process restarts |
| `src/models/opinion.py` | **NEW** | Dataclass for structured opinion results and `dedupe_sources()` utility |
| `personas/schema.json` | **NEW** | Formal JSON Schema (Draft 2020-12) for persona validation |
| `personas/*.json` (10 files) | **NEW** | Modular per-agent definitions (`dr_aris`, `prof_elena`, `hybrid_architect`, `systems_specialist`, `grad_student`, etc.) |
| `src/personas/loader.py` | **NEW** | Validated persona loader using `jsonschema` with cross-repo field alias harmonization |
| `prompts/system.jinja` | **MODIFIED** | Upgraded with prompt-injection defenses, conditional `memory_summary` rendering, and 5-web-search limit notice |
| `prompts/opinion.jinja` | **MODIFIED** | Formatted with grounded evidence titles, URLs, and stance priorities |
| `src/prompts/builder.py` | **NEW** | Programmatic prompt assembler with `tools_available` flag to avoid provider 400 errors |
| `src/pipelines/opinion.py` | **NEW** | Deterministic retrieval-first opinion pipeline with strict `[Source: URL]` citation validation |
| `src/utils/debug_trace.py` | **MODIFIED** | **Trace Deduplication & Organization:** Eliminated 4x document text redundancy; created clean bibliography `grounded_sources`, structured `tool_calls`, and human-readable `messages_transcript`; reduced trace file size by >55% |
| `src/utils/graph_utils.py` | **MODIFIED** | Added `validate_neighbor_opinions()` to prevent neighbor spoofing in topology |
| `src/handoff.py` | **NEW** | Single-function entry point (`get_response`) for Week 3 multi-agent orchestration |
| `demo.py` | **MODIFIED** | Upgraded to run 5 independent personas concurrently; outputs **dual JSON files** (`*-demo.json` opinions summary and `*-trace.json` full auditable trace) |
| `cli.py` | **NEW** | Interactive CLI runner supporting `--topic`, `--personas`, `--top-k`, and `--skip-memory-demo` |
| `tests/test_tools.py` | **NEW** | 11 new tests covering pgvector RAG, web search capping, and LLM query reformulation |

---

## 2. Key Enhancements by Feature

### 1. LLM Engine: Weights & Biases (`wandb`) Integration
* **Provider:** `wandb`
* **Model:** `Qwen/Qwen3.6-35B-A3B` (MoE with 3B active / 35B total parameters, 262k context window)
* **Endpoint:** `https://api.inference.wandb.ai/v1`
* **Optimization:** `reasoning_effort="none"` is configured directly in `ChatOpenAI`. This bypasses verbose internal thinking loops, ensuring fast, deterministic tool execution without token limit exhaustion.

### 2. Retrieval: Automatic LLM Query Reformulation
* **Trigger:** When pgvector retrieval yields **0 chunks** or has **weak cosine similarity (`distance > 0.40`)**.
* **Action:** `_regenerate_query_with_llm()` automatically invokes the LLM to rewrite the query into 6–12 dense, domain-specific architecture keywords.
* **Audit Trail:** If the retry improves relevance, the new chunks are adopted and the trace records `"query_regenerated": true` with both original and new queries.

### 3. Search Throttling: Max 5 Web Searches per Run
* **Implementation:** `MAX_WEB_SEARCHES_PER_RUN = 5` enforced in `tool_node` in `src/agent/graph.py`.
* **Behavior:** When an agent attempts more than 5 searches, a polite notification prompts the agent to synthesize its position using already retrieved evidence.

### 4. 100% Untruncated Chunk Text Logging
* Removed character clamps (`[:600] + "... (truncated)"`) in `src/tools/retrieval_tool.py` and `src/search/base.py`.
* Full multi-paragraph text is preserved verbatim in `AgentState["retrieved_docs"]` and saved to output JSON logs.

### 5. Trace Deduplication & Clean Organization
* **Problem Solved:** Document chunks were previously duplicated 4x across `retrieved_docs`, `web_documents`, `grounded_sources`, `tool_calls.raw_output`, and `messages_transcript.content` (causing 670 KB+ bloat).
* **New Organized Schema:**
  - `retrieved_docs`: Canonical store for full untruncated pgvector chunks.
  - `web_documents`: Canonical store for full untruncated web search results.
  - `grounded_sources`: Clean, deduplicated bibliography (title, URL, tool, score, concise preview) without repeating multi-KB chunk bodies.
  - `tool_calls`: Structured invocation records (status, documents returned count, argument details, execution summary).
  - `messages_transcript`: Clean, human-readable conversation transcript with compact tool references.
* **Result:** **>55% file size reduction** (from 671 KB down to ~302 KB) with zero data loss.

### 6. 5-Persona Independent Opinions Demo
* Executes 5 distinct personas on the 1B Transformer architecture challenge:
  1. **Dr. Aris Thorne** (Pragmatic MoE & Efficiency Advocate)
  2. **Prof. Elena Vance** (Academic Skeptic & Theoretical Purist)
  3. **Dr. Samira Chen** (Hybrid Architecture Specialist)
  4. **Systems & Kernels Engineer** (CUDA, Memory Bandwidth & Hardware Utilization)
  5. **Leo Kowalski** (PhD Student, SOTA Benchmark Chaser)
* **Thread Isolation:** Each persona runs in its own thread (`demo_agent_<id>`) with clean initial state.
* **Outputs:** Dual JSON files generated under `outputs/opinions/`:
  - `<timestamp>-demo.json`: High-level summary of all 5 opinions and follow-up memory check.
  - `<timestamp>-trace.json`: Comprehensive, deduplicated audit log.

---

## 3. Test Suite Verification

All **40 unit and integration tests** pass completely offline:

```bash
$ .venv/bin/pytest tests/ -v
============================== 40 passed in 1.78s ==============================
```

- **`tests/test_graph.py`**: 3 passed
- **`tests/test_handoff.py`**: 1 passed
- **`tests/test_memory.py`**: 3 passed
- **`tests/test_memory_window.py`**: 2 passed
- **`tests/test_opinion.py`**: 4 passed
- **`tests/test_personas.py`**: 5 passed
- **`tests/test_prompts.py`**: 3 passed
- **`tests/test_retrieval.py`**: 4 passed
- **`tests/test_tools.py`**: 11 passed
- **`tests/test_web_search.py`**: 4 passed
