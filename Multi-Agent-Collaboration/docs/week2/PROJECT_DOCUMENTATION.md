# Week 2: Intelligent Agent Framework — Project Documentation

## 1. Overview

This document provides a comprehensive overview of **Week 2** of the Qubeterra AI NextGen Program. It explains the project's goals, the architecture of the agent framework, its integration with the Week 1 knowledge infrastructure, and step‑by‑step instructions for running the system.

**Week 2** transforms the retrieval system built in Week 1 into a **configurable multi‑agent framework**. The agents are persona‑driven, maintain memory across interactions, use external tools (including the Week 1 RAG system), and generate grounded opinions about a given topic.

The final deliverable is a reusable agent framework that will be used in Week 3 to power a multi‑agent debate system.

---

## 2. Program Context

This project is part of the **Qubeterra AI NextGen Program**, a 5‑week fellowship where participants build a complete, deployed Multi‑Agent Opinion Simulation Platform.

The program is structured as follows:

| Week | Milestone | Description |
|------|-----------|-------------|
| 1 | **Knowledge Infrastructure** | Build a RAG pipeline: collect, clean, chunk, embed, and store documents in PostgreSQL with pgvector. |
| 2 | **Intelligent Agent Framework** | Build configurable AI agents with personas, memory, tools, and initial opinion generation. |
| 3 | Multi‑Agent Collaboration Engine | Create a live discussion engine where multiple agents debate and evolve opinions. |
| 4 | Analytics & Intelligence Layer | Measure opinion change, agreement, and influence between agents. |
| 5 | Frontend, Deployment & Production | Wrap everything into a live web app, containerized and deployed. |

This document focuses on **Week 2**.

---

## 3. Week 1: Knowledge Infrastructure (The Foundation)

Before building the agents, we built a **knowledge base** that the agents will query for grounded evidence.

### 3.1 What Week 1 Built

- **Data Collection**: 911 raw documents (papers, blog posts, explainers) from sources like arXiv, Hugging Face, Mistral AI, and research blogs.
- **Cleaning & Filtering**: 331 on‑topic documents survived relevance filtering.
- **Chunking**: 16,669 chunks (1200 chars max, 300 overlap) to preserve semantic meaning.
- **Embeddings**: Each chunk was embedded using `all‑MiniLM‑L6‑v2` (384 dimensions).
- **Storage**: Chunks, embeddings, and metadata were stored in **PostgreSQL with pgvector**.
- **Retrieval**: Hybrid search (vector + text) with Reciprocal Rank Fusion (RRF) returns ranked, cited results.

### 3.2 Week 1's Retrieval Interface

Week 1 exposes a Python function `retrieve(query, top_k, rerank)` that returns a list of chunks with:
- `text`: The chunk content.
- `url`: Source URL.
- `title`: Document title.
- `similarity`: Cosine similarity (vector search).
- `text_rank_score`: Full‑text search rank.
- `rrf_score`: Combined RRF score.

To make this available to Week 2, we wrapped it in a **FastAPI** REST endpoint.

---

## 4. Week 2: Intelligent Agent Framework

### 4.1 Project Goal

Build a **reusable, configurable AI agent framework** that:
- Represents distinct personas (configurable via JSON).
- Maintains **two types of memory**:
  - **Internal memory**: conversation history (persisted via LangGraph checkpointer).
  - **External memory**: opinions of neighbouring agents (injected from outside).
- Uses **tools** (the Week 1 RAG system and a live web search).
- Decides **when** to use tools (ReAct agent loop).
- Generates a **grounded initial opinion** for a given project specification.

### 4.2 High‑Level Architecture

The agent is built using **LangGraph** – a framework for stateful, cyclic, multi‑actor applications.

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentState                            │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Internal Memory │  │  External Memory │               │
│  │  (messages)      │  │ (neighbor_opinions)│             │
│  └──────────────────┘  └──────────────────┘               │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Persona         │  │  Task            │               │
│  │  (config)        │  │  (specification) │               │
│  └──────────────────┘  └──────────────────┘               │
│  ┌──────────────────┐                                    │
│  │  final_opinion   │                                    │
│  └──────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────┐
              │   LangGraph     │
              │   ReAct Loop    │
              │                 │
              │  agent node ◄───│── tools node
              │  (LLM decides) │   (executes tools)
              └─────────────────┘
                         │
                         ▼
              ┌─────────────────┐
              │   Final Opinion │
              │   (grounded &   │
              │    cited)       │
              └─────────────────┘
```

### 4.3 Components

#### 4.3.1 Persona Configuration (JSON)

Personas are defined in `personas/personas.json`. Each persona includes:

```json
{
  "id": "dr_aris",
  "name": "Dr. Aris Thorne",
  "background": "Senior Research Scientist at a leading cloud AI lab...",
  "stance": "Advocates strongly for Sparse MoE and SSM...",
  "style": "Data-driven, pragmatic...",
  "expertise": ["Mixture of Experts", "Model Compression", ...],
  "priorities": "FLOPs reduction, memory bandwidth optimization...",
  "retrieval_focus": "MoE scaling laws, SSM efficiency benchmarks..."
}
```

The `retrieval_focus` field guides the agent's queries to the knowledge base, ensuring each persona retrieves evidence aligned with its stance.

#### 4.3.2 Memory (Two Types)

| Memory Type | Key in State | Managed By | Purpose |
|-------------|--------------|------------|---------|
| **Internal** | `messages` | LangGraph checkpointer | Conversation history with tools calls/results. |
| **External** | `neighbor_opinions` | Injected from outside | Opinions of other agents (Week 3). |

#### 4.3.3 Tools

| Tool | File | Purpose |
|------|------|---------|
| `knowledge_retrieval` | `src/tools/retrieval_tool.py` | Calls Week 1 FastAPI endpoint. |
| `live_web_search` | `src/tools/search_tool.py` | Searches the web (DuckDuckGo or Tavily). |
| `deep_web_crawl` | `src/tools/crawl_tool.py` | Crawls a specific URL for full‑text extraction. |

The agent **decides** which tools to use and when, using a ReAct loop.

#### 4.3.4 Prompt Templates (Jinja2)

All prompts are stored in `prompts/`:

- `system.jinja`: Injected into every LLM call (includes persona, neighbor opinions, task, tool descriptions).
- `opinion.jinja`: Used for generating the final opinion (optional, currently the system prompt suffices).

The prompts are **dynamically rendered** from the persona config—no hardcoded behavior.

#### 4.3.5 LLM Provider (Pluggable)

The LLM provider is configured via environment variables:

| Variable | Values | Description |
|----------|--------|-------------|
| `LLM_PROVIDER` | `openrouter`, `ollama` | Which provider to use. |
| `LLM_MODEL` | Provider‑specific | Model name. |
| `OPENROUTER_API_KEY` | (for OpenRouter) | API key. |
| `OLLAMA_BASE_URL` | (for Ollama) | Base URL (e.g., ngrok endpoint). |

The factory `src/llm/factory.py` returns a LangChain `BaseChatModel`, allowing tool calling (`bind_tools`).

---

## 5. Integration with Week 1

### 5.1 Week 1 Exposed as a Service

Week 1's retrieval function is wrapped in a FastAPI app (`app.py`) that exposes:

- `GET /health` – returns index metadata (row count, source count, embedding model).
- `POST /retrieve` – accepts a JSON payload `{"query": "...", "top_k": 5, "rerank": false}` and returns a list of results with citations.

The FastAPI server runs locally (or via ngrok) and is accessed by Week 2's `knowledge_retrieval` tool.

### 5.2 Week 2's Retrieval Tool

The tool `knowledge_retrieval` (in `src/tools/retrieval_tool.py`) sends a POST request to the FastAPI endpoint, formats the response into a string with source citations, and returns it to the agent.

**Environment Variable**: `RAG_API_BASE` (default `http://localhost:8000`).

---

## 6. Repository Structure

```
week2/
├── .env.example                 # Environment variables template
├── .gitignore
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
│
├── personas/
│   └── personas.json            # 4 persona configurations
│
├── prompts/
│   ├── system.jinja             # System prompt template
│   └── opinion.jinja            # Opinion generation template
│
├── src/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py             # AgentState TypedDict
│   │   └── graph.py             # LangGraph ReAct graph
│   ├── llm/
│   │   ├── __init__.py
│   │   └── factory.py           # Pluggable LLM factory
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── retrieval_tool.py    # Week 1 RAG integration
│   │   ├── search_tool.py       # Live web search
│   │   └── crawl_tool.py        # Deep URL crawling
│   ├── search/
│   │   ├── __init__.py
│   │   ├── base.py              # SearchProvider abstraction
│   │   ├── duckduckgo.py        # DuckDuckGo implementation
│   │   ├── tavily.py            # Tavily implementation
│   │   ├── crawl4ai.py          # Crawl4AI implementation
│   │   └── factory.py           # Search provider factory
│   └── utils/
│       ├── __init__.py
│       └── prompt_loader.py     # Jinja2 template loader
│
├── tests/
│   ├── test_memory.py           # Memory persistence tests
│   └── test_tools.py            # Tool unit tests
│
└── demo.py                      # Full demonstration script
```

---

## 7. Installation & Setup

### 7.1 Prerequisites

- Python 3.11 or higher.
- PostgreSQL (local or Docker) with the `pgvector` extension.
- (Optional) ngrok for exposing the FastAPI endpoint.

### 7.2 Clone the Repository

```bash
git clone <week2-repo-url>
cd week2
```

### 7.3 Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
```

### 7.4 Install Dependencies

```bash
pip install -r requirements.txt
```

### 7.5 Configure Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# LLM Provider
LLM_PROVIDER=ollama                     # or openrouter
LLM_MODEL=gemma3:4b                     # Provider-specific

# For Ollama (if using)
OLLAMA_BASE_URL=http://localhost:11434  # or your ngrok URL

# For OpenRouter (if using)
OPENROUTER_API_KEY=your_key_here
# LLM_MODEL=google/gemma-4-26b-a4b-it:free

# RAG API (Week 1 FastAPI)
RAG_API_BASE=http://localhost:8000      # or ngrok URL

# Search Provider
SEARCH_PROVIDER=duckduckgo              # or tavily
# TAVILY_API_KEY=your_key_here
```

---

## 8. Running the Week 1 FastAPI Server

**Important:** The Week 2 agents need the Week 1 API to be running.

### 8.1 Start the FastAPI Server

Navigate to your Week 1 repository:

```bash
cd ../week1
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 8.2 Verify the API is Working

```bash
curl http://localhost:8000/health
```

Expected output:

```json
{
  "status": "healthy",
  "row_count": 16669,
  "source_count": 331,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_model_revision": "main"
}
```

### 8.3 (Optional) Expose via ngrok

If you need to access the API from outside your local machine:

```bash
ngrok http 8000
```

Copy the public URL (e.g., `https://abc123.ngrok-free.app`) and update `RAG_API_BASE` in Week 2's `.env`.

---

## 9. Running the Week 2 Agent Demo

### 9.1 Ensure the LLM Provider is Accessible

If using **Ollama**, ensure the server is running and the model is pulled:

```bash
ollama pull gemma3:4b   # or any other model
ollama serve
```

If using **OpenRouter**, ensure your API key is correct.

### 9.2 Run the Demo

From the Week 2 root directory:

```bash
python demo.py
```

### 9.3 What the Demo Does

1. Loads 4 personas from `personas/personas.json`.
2. Selects two personas (Dr. Aris Thorne and Prof. Elena Vance).
3. Defines a **project task** (e.g., "Build a Transformer with budget X, discuss MoE vs Dense...").
4. Runs **Agent A** (Dr. Aris Thorne) through the ReAct loop.
   - The agent decides whether to call `knowledge_retrieval`, `live_web_search`, or `deep_web_crawl`.
   - It retrieves evidence, processes it, and produces a final, cited opinion.
5. Captures Agent A's opinion and injects it as **external memory** (`neighbor_opinions`) for Agent B.
6. Runs **Agent B** (Prof. Elena Vance) with Agent A's opinion visible in its system prompt.
7. Demonstrates **internal memory** by asking Agent A a follow‑up question using the same `thread_id`. The agent remembers its previous response.

### 9.4 Expected Output

You should see:

- **Distinct opinions** from Agent A (pro‑MoE/SSM) and Agent B (pro‑dense/global attention).
- **Citations** in both opinions, referencing real arXiv papers and blog posts from your knowledge base.
- The memory test shows Agent A correctly summarising its earlier point.

---

## 10. Testing

### 10.1 Test the Retrieval Tool in Isolation

```bash
python -c "from src.tools.retrieval_tool import knowledge_retrieval; print(knowledge_retrieval('advantages of MoE'))"
```

You should see formatted results with source citations.

### 10.2 Run the Memory Test

```bash
python tests/test_memory.py
```

This simulates a conversation and verifies that the agent retains information across turns using the same `thread_id`.

### 10.3 Run the Tool Tests

```bash
python tests/test_tools.py
```

This tests that each tool returns the expected format.

---

## 11. Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Framework** | LangGraph | Built‑in state management, checkpointer for memory, native support for cyclic workflows (ReAct). |
| **Agent Type** | ReAct (Tool‑Calling) | The agent decides when to use tools, fulfilling the requirement. |
| **Memory** | Two‑state (`messages` + `neighbor_opinions`) | Separates internal conversation history from external shared memory. |
| **LLM Interface** | LangChain `BaseChatModel` | Unified tool calling (`bind_tools`), pluggable providers. |
| **Tools** | `@tool` decorator | Automatic schema generation, easy to add new tools. |
| **Prompts** | Jinja2 templates | No hard‑coded strings, maintainable, version‑controlled. |
| **Personas** | JSON configuration | Scalable to hundreds of agents, no code changes for new personas. |
| **LLM Providers** | OpenRouter + Ollama | Supports both cloud and local deployment, tested working. |
| **Week 1 Integration** | FastAPI microservice | Clean decoupling, allows independent scaling and deployment. |

---

## 12. Handoff to Week 3

Week 3 will use the agents as participants in a multi‑agent debate. The Week 2 framework provides the following interface:

```python
from src.agent.graph import graph
from src.agent.state import AgentState

# Create an agent state
state = AgentState(
    task="...",
    messages=[],
    neighbor_opinions={},
    persona=persona_dict,
    final_opinion=""
)

# Invoke the graph
config = {"configurable": {"thread_id": "unique_thread_id"}}
result = graph.invoke(state, config)

# Extract the opinion
opinion = result["final_opinion"]
```

Week 3 will orchestrate multiple agents by:
1. Creating a state for each agent.
2. Running them sequentially or in rounds.
3. Injecting each agent's opinion into others' `neighbor_opinions`.
4. Repeating until consensus or a fixed number of rounds.

---

## 13. Known Limitations & Future Improvements

| Limitation | Future Improvement |
|------------|-------------------|
| LLM context window can be exceeded with long tool outputs. | Add a token‑counting summarisation step. |
| Search providers are synchronous. | Implement async versions. |
| Persona configurations are static (loaded once). | Add dynamic persona generation. |
| Memory is in‑memory (`MemorySaver`). | Use persistent storage (e.g., PostgreSQL) for long‑lived agents. |
| Crawl4AI tool is a stub. | Implement full crawling with robust error handling. |

---

## 14. Quick Reference: Commands

| Command | Description |
|---------|-------------|
| `uvicorn app:app --host 0.0.0.0 --port 8000 --reload` | Start Week 1 FastAPI server (from Week 1 repo). |
| `python demo.py` | Run the Week 2 agent demo. |
| `python -c "from src.tools.retrieval_tool import knowledge_retrieval; print(knowledge_retrieval('query'))"` | Test the RAG tool. |
| `python tests/test_memory.py` | Run memory persistence tests. |
| `ollama pull gemma3:4b` | Pull a model for local Ollama. |

---

## 15. Conclusion

Week 2 delivers a **production‑ready, configurable agent framework** that:
- Creates distinct, persona‑driven AI agents.
- Maintains two types of memory (internal and external).
- Uses real tools (RAG + web search) to ground its reasoning.
- Produces cited, evidence‑backed opinions.
- Is ready to be extended into a multi‑agent debate system in Week 3.

The integration with Week 1 is seamless via a FastAPI microservice, ensuring the knowledge base remains decoupled and independently deployable.

---

*Document created: 2026‑09‑04*  
*Version: 1.0*  
*Project: Qubeterra AI NextGen Program – Week 2*