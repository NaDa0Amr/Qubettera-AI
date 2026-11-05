# Qubettera

Qubettera is a retrieval-grounded, multi-agent AI discussion platform. It
collects and indexes research content, retrieves relevant evidence, and gives
that evidence to configurable persona agents that debate a topic over a
strongly connected graph.

The project includes a Python AI engine, FastAPI backend, Next.js dashboard,
PostgreSQL/pgvector knowledge base, discussion analytics, and Docker
deployment.

```text
question
   -> hybrid RAG retrieval
   -> cited evidence
   -> persona-based LLM agents
   -> graph-routed discussion rounds
   -> transcript, analytics, and visual reports
```

## Highlights

- Retrieval-augmented generation using Qwen3 embeddings and PostgreSQL/pgvector.
- Hybrid vector and PostgreSQL keyword retrieval with reciprocal-rank fusion.
- Configurable persona agents with ring, star, fully connected, and
  expertise-based graph topologies.
- Multi-round discussions with concurrent agent execution and a moderator
  synthesis.
- Citation validation, evidence tracking, retrieval warnings, and persisted
  JSONL discussion histories.
- Real-time discussion and analytics streaming through Server-Sent Events.
- Analytics for opinion change, agreement, influence, sentiment, and
  interaction graphs.
- Generated JSON results, Markdown reports, and PNG visualizations.
- Local, hosted, and OpenAI-compatible LLM provider support.
- Docker Compose deployment with persistent PostgreSQL and model-cache volumes.

## Architecture

```text
Next.js / React UI
        |
        v
FastAPI API + SSE endpoints
        |
        v
Qubettera Python engine
  |        |          |
  v        v          v
RAG     LangGraph   Analytics
  |        |
  v        v
PostgreSQL/pgvector  LLM provider
```

The shared engine is located in `src/qubettera/`. The web application is split
between `backend/` and `frontend/`, while `resources/` contains persona,
prompt, and graph configuration.

## Technology stack

| Area | Technologies |
| --- | --- |
| AI orchestration | Python, LangChain, LangGraph, Jinja2 |
| LLM providers | Ollama, OpenRouter, Groq, W&B Inference, Kaggle/Ollama-compatible endpoints |
| Retrieval | Qwen3 embeddings, Sentence Transformers, PostgreSQL, pgvector, reciprocal-rank fusion |
| Search and crawling | DuckDuckGo, Tavily, Crawl4AI, Scrapling |
| Analytics | Hugging Face Transformers, PyTorch, NetworkX, Pillow |
| Backend | FastAPI, Uvicorn, Pydantic |
| Frontend | Next.js, React, TypeScript, Tailwind CSS, Recharts |
| Testing | Pytest, pytest-asyncio, HTTPX, Playwright, ESLint, TypeScript |
| Deployment | Docker, Docker Compose, Docker Hub |

## Docker images

Published Docker images:

- 🐳 [Backend image](https://hub.docker.com/r/nada123456aa/qubettera-backend): [`nada123456aa/qubettera-backend`](https://hub.docker.com/r/nada123456aa/qubettera-backend)
- 🐳 [Frontend image](https://hub.docker.com/r/nada123456aa/qubettera-frontend/tags): [`nada123456aa/qubettera-frontend:0.1.0`](https://hub.docker.com/r/nada123456aa/qubettera-frontend/tags)

To pull the published images:

```bash
docker pull nada123456aa/qubettera-backend
docker pull nada123456aa/qubettera-frontend:0.1.0
```

For the complete PostgreSQL, backend, and frontend stack, configure the root
`.env` file and run:

```bash
docker compose up --build -d --wait
```

The Docker setup includes:

- PostgreSQL with the pgvector extension.
- FastAPI backend on port `8000`.
- Next.js frontend on port `3000`.
- Persistent database, research-data, discussion-output, and model-cache
  storage.
- Optional Ollama deployment using `docker-compose.ollama.yml`.

See [Docker deployment documentation](docs/docker.md) for publishing,
containerized Ollama, health checks, and smoke testing.

## Local setup

### Requirements

- Python 3.11–3.13
- Node.js 20.9 or newer
- PostgreSQL 17 with pgvector, or Docker
- An LLM provider configured in `.env`

### Install

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -e ".[web,analytics,dev]"
npm --prefix frontend ci
cp .env.example .env                   # Windows: Copy-Item .env.example .env
```

Update `.env` with the database password and the LLM provider settings. The
default configuration supports a Kaggle/Ollama-compatible endpoint. Ollama,
Groq, OpenRouter, and W&B Inference can be selected with `LLM_PROVIDER`.

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Start the API:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```bash
npm --prefix frontend run dev
```

Open [http://localhost:3000](http://localhost:3000). FastAPI's interactive
documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## RAG pipeline

The RAG pipeline collects research sources, cleans and chunks documents,
creates embeddings, stores them in PostgreSQL/pgvector, and evaluates retrieval
quality.

```bash
qubettera rag pipeline
qubettera rag pipeline --skip-collection
qubettera rag retrieve "mixture of experts routing" --top-k 5
qubettera rag retrieve "mixture of experts routing" --adaptive-expand
qubettera rag evaluate --mode hybrid
qubettera rag evaluate --mode adaptive
```

The default embedding model is `Qwen/Qwen3-Embedding-0.6B`. Embeddings are
generated incrementally and can resume from cached output after interruption.

## Discussions

Run a deterministic discussion without an external model:

```bash
qubettera discuss run --mode fake
```

Run a live discussion with the configured provider:

```bash
qubettera discuss run --mode live
qubettera discuss run --mode live --analyze
```

The standard configuration creates five opening opinions, three discussion
rounds, and a moderator synthesis. Each round uses a snapshot of the previous
round, preventing same-round response leakage. Responses are required to use
exact `[Source: URL]` citations when evidence is available.

Individual agent opinions can also be generated from the CLI:

```bash
qubettera agent opinion dr_aris "Dense versus sparse transformer layers"
```

## Analytics

Analytics consumes a completed live discussion log and produces a JSON summary,
Markdown report, and PNG visualizations:

```bash
qubettera analytics run outputs/discussions/<discussion-id>.jsonl
```

The analytics pipeline measures:

- Opinion stance and change between rounds.
- Agreement between participant positions.
- Influence across routed graph edges.
- Sentiment at message, agent, and round level.

Fake discussions are intended for orchestration and UI testing and are rejected
by the analytics loader because they do not contain real opinions.

## API and frontend routes

| Route | Purpose |
| --- | --- |
| `/` | Project introduction and persona overview |
| `/discussions` | Start discussions, view history, and browse personas |
| `/discussions/[id]` | Live or saved discussion transcript |
| `/analytics` | Saved analytics overview |
| `/analytics/[discussionId]` | Metrics, reports, and visualizations |
| `/docs` | Interactive FastAPI API documentation |
| `/health` | Liveness check |
| `/health/ready` | Local readiness check |

Discussion and analytics updates are streamed using Server-Sent Events. The
frontend proxies requests to the FastAPI backend and maintains separate
streaming state for concurrent participant responses.

## Testing and verification

Backend tests:

```bash
python -m pytest
python -m pytest tests/test_web_integration.py
python -m pytest tests/analytics -q
```

Frontend checks:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:smoke
```

Container smoke test:

```bash
python scripts/docker-smoke.py --namespace nada123456aa --tag 0.1.0
```

The smoke test checks service health, frontend proxying, fake discussions,
history persistence after restart, pgvector availability, CLI installation,
non-root container permissions, CPU PyTorch, and Chromium.

## Repository layout

```text
backend/       FastAPI application and API services
frontend/      Next.js user interface
src/qubettera/ Shared AI, RAG, discussion, and analytics engine
resources/     Personas, prompts, schemas, and runtime configuration
tests/         Backend, agent, RAG, discussion, analytics, and integration tests
docs/          Architecture, deployment, RAG, and analytics documentation
scripts/       Docker smoke tests and deployment helpers
outputs/       Discussion, opinion, memory, and analytics artifacts
```

## Configuration

Copy `.env.example` to `.env`. Important settings include:

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | Selects the configured generation provider |
| `KAGGLE_LLM_URL` / `KAGGLE_LLM_MODEL` | Kaggle/Ollama-compatible generation endpoint |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Local or remote Ollama model |
| `OPENROUTER_API_KEY` | OpenRouter access |
| `GROQ_API_KEY` / `GROQ_MODEL` | Groq access |
| `WANDB_API_KEY` / `WANDB_MODEL` | W&B Inference access |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | PostgreSQL connection |
| `EMBEDDING_MODEL` | Embedding model used by the RAG pipeline |
| `CHECKPOINT_BACKEND` | In-memory or PostgreSQL LangGraph checkpoints |
| `SEARCH_PROVIDER` | External search provider for agent tools |

Do not commit `.env` files, API keys, model credentials, or database passwords.

## License

No license file is currently included in this repository. Add a license before
redistributing the project or its source code.
