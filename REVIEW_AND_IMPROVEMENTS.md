# Qubettera Full Repository Review and Improvement Plan

Review date: 2026-09-22

## Executive summary

The repository now has a sensible unified shape: one installable `qubettera`
package, one CLI, shared resources, a local MiniLM/PostgreSQL RAG subsystem, a
Kaggle-hosted generation model, and a deterministic multi-agent discussion
orchestrator. The automated suite is healthy (`138 passed, 1 skipped`). All 19
JSON resource/baseline files parse, and all 11 individual personas validate.

The system is not yet production-ready. The most important remaining problems
are migrated paths that still resolve to old or incorrect locations, discussion
retrieval queries that can exceed the retriever's hard limit and silently lose
evidence, a relevance check that reads a score field the retriever does not
produce, and the absence of real Postgres/Kaggle integration tests.

Recommended order:

1. Fix the four P0 correctness items below.
2. Add live-service contract tests and improve `doctor`.
3. Pool/batch retrieval work and measure quality against the stored baseline.
4. Harden the remote endpoint and crawler before exposing the program as a
   service.
5. Remove legacy coursework terminology and duplicate utilities.

## Review scope and validation

Reviewed:

- All Python source under `src/qubettera/`.
- All tests under `tests/`.
- Root packaging, environment, Docker, CLI, and ignore configuration.
- Persona, graph, discussion, schema, and prompt resources.
- Current RAG collection and evaluation baseline reports.
- Archived documentation for stale paths and conflicting architecture claims.

Validation performed:

- `python -m pytest -q -p no:cacheprovider -rs`
  - Result: `138 passed, 1 skipped`.
  - The skip is the Scrapling import test because Scrapling is not installed in
    the active global Python environment.
- Imported/compiled the unified package during testing.
- Parsed every JSON file in `resources/` and `docs/baselines/`.
- Validated all individual personas through the production persona loader.
- Ran `git diff --check` and reviewed repository status.
- Ran the CLI readiness check. Postgres was unavailable and
  `langchain_ollama` was not installed in the active environment, so a true
  Kaggle/Postgres end-to-end execution could not be completed.

Generated corpus contents under `data/` were not manually reviewed document by
document. Their pipeline metadata and stored evaluation report were reviewed.

## P0: correctness issues to fix first

### 1. Discussion queries can exceed the retriever limit and silently disable RAG

Evidence:

- `src/qubettera/discussion/retrieval_provider.py:20` allows 1,800 characters.
- `src/qubettera/discussion/retrieval_provider.py:66-90` combines the objective,
  topic, constraint, persona focus, previous opinion, and neighbor opinions.
- `src/qubettera/rag/retrieve.py:100-101` rejects anything over 512 characters.
- `src/qubettera/discussion/retrieval_provider.py:95-108` catches that
  `ValueError` and returns no evidence, allowing the discussion to continue as
  if retrieval merely found nothing.

Impact: later rounds are particularly likely to cross 512 characters. Those
turns receive no fresh RAG evidence even though their event is reported as a
successful agent turn.

Recommended change:

- Make one shared query limit constant and enforce it while constructing the
  query, not after construction.
- Prefer objective + current topic + persona focus + extracted keywords from
  neighbor claims. Do not concatenate long opinions verbatim.
- Record retrieval status (`ok`, `empty`, `invalid_query`, `unavailable`) in
  turn metadata and the event log.
- Add a regression test using realistic maximum-length previous and neighbor
  opinions, asserting that the final query is valid and retrieval is invoked.

Acceptance criterion: every live discussion turn issues a query accepted by
`_validate_query`, or explicitly records why it did not.

### 2. Retrieval quality fallback checks a field that is never returned

Evidence:

- `src/qubettera/agents/tools/retrieval_tool.py:60-64` treats results as relevant
  whenever `distance` is absent.
- `src/qubettera/rag/retrieve.py:212-290` returns `similarity`, `rrf_score`, and
  optionally `text_rank_score`; it does not return `distance`.

Impact: every non-empty retrieval result is accepted, even when similarity is
weak. The intended LLM query rewrite path will only activate for an empty
result set, not for poor matches.

Recommended change:

- Define a single score contract for retrieval results. For example, preserve
  `similarity`, `rrf_score`, and `rerank_score` with documented directions and
  ranges.
- Base weak-result detection on calibrated similarity or reranker thresholds.
- Do not compare RRF, cosine similarity, and distance as interchangeable values.
- Tune the threshold on labeled queries rather than keeping the current hard
  coded `0.40` rule.

Acceptance criterion: tests demonstrate distinct behavior for high-quality,
weak, and empty result sets using the actual production result shape.

### 3. Several default paths still point to the wrong post-migration locations

Confirmed at runtime:

- Canonical root: `C:\Qubettera AI`.
- `AgentMemory` default: `C:\Qubettera AI\src\qubettera\outputs\memory`.
- Legacy web-search root: `C:\Qubettera AI\src\qubettera`.
- Legacy graph-utility root: `C:\Qubettera AI\src\qubettera`.

Locations:

- `src/qubettera/agents/memory/agent_memory.py:16-17` computes the wrong root.
- `src/qubettera/agents/web_search.py:17-32` looks for `.env` below the package,
  not at the repository root.
- `src/qubettera/agents/utils/graph_utils.py:19` computes the wrong root.
- `src/qubettera/agents/handoff.py:58-60` defaults to the removed
  `personas/debate_graph.json` path.
- RAG stages use `Path("data/...")`, so behavior depends on the caller's current
  working directory rather than `qubettera.paths.DATA_DIR`.

Impact: commands can write to unexpected directories or fail when launched
outside the repository root. The handoff path fails whenever neighbor opinions
are supplied without an explicit topology path.

Recommended change:

- Import all paths from `qubettera.paths`; remove local `PROJECT_ROOT`
  calculations.
- Use `DATA_DIR`, `OUTPUTS_DIR`, `PERSONAS_DIR`, and `CONFIGS_DIR` everywhere.
- Load `.env` once from `PROJECT_ROOT / ".env"` at the application boundary.
- Make direct module execution either officially supported and tested from a
  foreign working directory, or remove the `sys.path` manipulation and support
  only `python -m qubettera...` / `qubettera`.

Acceptance criterion: CLI commands and public APIs behave identically when the
current directory is outside the repository.

### 4. The default memory store is not safe enough for concurrent production use

Evidence:

- The incorrect output path is described above.
- `src/qubettera/agents/memory/agent_memory.py:44` creates one lock per Python
  object. Two instances for the same agent do not share that lock, and separate
  processes are completely uncoordinated.
- `src/qubettera/agents/memory/agent_memory.py:75-80` silently skips malformed
  JSONL rows.
- `recent(0)` returns every item because Python evaluates `entries[-0:]` as
  `entries[0:]`.

Impact: concurrent writers can interleave records, corrupted records can be
silently hidden, and a caller requesting zero recent records gets the entire
history.

Recommended change:

- Correct the path and validate `limit >= 0` (`0` should return an empty list).
- Use a process-safe file lock or store memory in PostgreSQL.
- Report corrupt lines with path and line number using the strict JSONL helper.
- Add same-agent multi-instance and multi-thread tests.

## P1: high-value improvements

### 5. `retrieve_batch` does not batch and every turn opens a new DB connection

`src/qubettera/rag/retrieve.py:402-418` loops through `retrieve` one query at a
time. Each call encodes one query and opens a new PostgreSQL connection. A
five-agent, three-round run produces 20 turns (five initial + fifteen discussion
turns), so connection/model overhead is repeated heavily.

Recommended change:

- Encode a stage's queries in one `SentenceTransformer.encode` call.
- Use a bounded PostgreSQL connection pool.
- Add a stage-level retrieval API to the orchestrator, then execute generation
  concurrently after evidence is ready.
- Cache normalized query embeddings and short-lived retrieval results.
- Measure p50/p95 per-stage latency before and after; do not rely only on total
  demo time.

### 6. Retrieval quality needs another tuning cycle

The stored complete baseline contains 15,162 chunks and 297 sources. At `k=5`:

| Mode | Hit@5 | Precision@5 | MRR | nDCG@5 | Source recall | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid | 0.6000 | 0.1400 | 0.3522 | 0.2808 | 0.3500 | 394.62 ms |
| Hybrid + rerank | 0.4667 | 0.1200 | 0.2872 | 0.2386 | 0.3000 | 1982.06 ms |

The reranker is about five times slower and lowers every reported quality
metric, so keeping reranking disabled by default is correct.

Recommended experiments:

- Inspect failures per query before changing algorithms.
- Measure actual tokenizer truncation for 1,200-character chunks plus contextual
  prefixes.
- Tune chunk size/overlap, RRF `k`, candidate pool, and source limits through a
  small grid search.
- Compare PostgreSQL full-text configurations for technical terms, acronyms,
  model names, and hyphenated tokens.
- Expand qrels beyond source-level matching to passage-level relevance.
- Add a minimum quality gate so regressions fail CI.

### 7. `doctor` checks construction, not real service health

`src/qubettera/cli.py:102-119` validates the index with a database query but only
constructs the generation client. A dead, expired, or incompatible Kaggle
tunnel may still be reported as healthy.

Recommended change:

- Check the configured Kaggle endpoint with a low-cost model-list or minimal
  generation request and a short timeout.
- Validate model name, context setting, authentication, and tool-calling support.
- Report dependency availability separately from endpoint availability.
- Add `--offline` and `--json` modes for CI and automation.

### 8. Live integration contracts are untested

The unit tests mock the database, retrieval service, LLM, search providers, and
crawler. There is no automated contract test for PostgreSQL/pgvector, the
Kaggle Ollama-compatible endpoint, or a complete live discussion.

Recommended test layers:

- Fast unit suite: current default.
- Docker integration suite: create a small index, retrieve known passages, and
  verify atomic index replacement.
- Kaggle contract suite: opt-in, one tiny prompt, verifies response and tool-call
  formats.
- End-to-end smoke suite: two agents, one round allowed by a test-specific
  configuration, fixed miniature corpus.
- Nightly/full evaluation: enforce retrieval-quality and latency thresholds.

### 9. Remote endpoint and crawler hardening

- Kaggle/tunnel configuration has no explicit authentication-header mechanism.
  A public tunnel can expose model capacity and discussion content.
- `deep_web_crawl` accepts an arbitrary model-provided URL. If this code becomes
  an API/service, it creates an SSRF path to localhost, private networks, and
  cloud metadata endpoints.
- Retrieved webpages are untrusted content. They can contain prompt-injection
  instructions, while the current prompt explicitly labels neighbor messages
  as untrusted but not tool content.

Recommended change:

- Support bearer/custom headers through secret environment variables, require
  HTTPS outside local development, and avoid logging secrets.
- Permit only `http`/`https`; resolve and reject loopback, private, link-local,
  and metadata IP ranges; optionally use a source-domain allowlist.
- Cap redirects, response bytes, and crawl duration.
- Mark retrieved content as quoted untrusted data in prompts and instruct the
  model never to follow embedded instructions.

### 10. Pin runtime and model identities for reproducibility

`pyproject.toml` leaves many fast-moving dependencies unbounded, and model
revision defaults are `main`. Docker uses the mutable `pgvector/pgvector:pg17`
tag.

Recommended change:

- Generate and commit a lock file for the supported Python/platform setup.
- Add compatible lower and upper bounds for direct dependencies.
- Pin Hugging Face model revisions to commit hashes.
- Pin the Docker image by version and preferably digest.
- Record Python, package, CUDA/CPU, model revision, and DB extension versions in
  evaluation output.

## P2: maintainability and product improvements

### 11. Remove duplicate and legacy code paths

There are overlapping implementations for web search, graph handling, prompt
construction, and command execution. Thirty source/README files still contain
old `Week N`, `Task N`, removed path, or direct-script terminology.

Candidates to consolidate:

- `agents/web_search.py` versus `agents/search/tavily.py`.
- `agents/utils/graph_utils.py` versus `discussion/agent_graph.py` and
  `agents/graph_builder.py`.
- Python prompt builders versus the active Jinja templates.
- Root compatibility scripts versus the `qubettera` console command.
- `Week2AgentRuntime`, `week2_adapter.py`, and assignment-oriented docstrings.

Choose one canonical implementation for each concept, deprecate it for one
release if needed, and then delete it. This will reduce inconsistent behavior
and make imports cheaper. In particular, `llm/factory.py` should import
`AgentCallbackHandler` directly instead of importing the broad `utils` package.

### 12. Fix smaller control-flow edge cases

- `agents/agent/graph.py:166-171` references `task` before assigning it if the
  message list is empty. Assign `task` before the fallback branch.
- `discussion/orchestrator.py:65` uses `max_workers or ...`; an explicit zero is
  ignored instead of triggering the documented validation. Test `is None`.
- Validate `MAX_TOOL_ROUNDS` as a non-negative integer.
- A single model response can request multiple retrieval tools before the next
  tool-round check. Add an overall tool-call/retrieval budget, not just a round
  counter.
- `DiscussionConfig` requires at least three rounds. Make the core library allow
  one or more rounds and enforce a three-round assignment/demo requirement only
  in the demo configuration.
- `model_config` is persisted in discussion configuration but does not actively
  configure the runtime. Either implement it or rename it to clarify that it
  only documents environment-variable names.

### 13. Improve failure policy and observability

Discussion retrieval failures currently log a warning and return no evidence.
That availability choice is reasonable, but it conflicts with strict prompts
that require grounded claims and is not obvious in the final status.

Recommended change:

- Add `RETRIEVAL_FAILURE_POLICY=fail|continue`.
- Persist retrieval status, latency, result count, score summary, model latency,
  token usage, retry count, and tool count per turn.
- Add an end-of-run summary containing evidence coverage per agent/round.
- Use structured logging with discussion and agent IDs.
- Redact credentials, signed URLs, and sensitive prompt content where needed.

### 14. Add a final team synthesis stage

The current result is an ordered transcript. It does not produce a final team
decision that summarizes consensus, disagreements, evidence, risks, and the
recommended architecture.

Add a deterministic synthesis contract after the final round, ideally with:

- selected recommendation;
- agreed constraints;
- unresolved disagreements;
- cited supporting and contradicting evidence;
- confidence/uncertainty;
- implementation checklist.

Validate citations against URLs actually present in the discussion evidence.

### 15. Add engineering quality gates

Recommended tooling:

- Ruff for formatting, imports, and linting.
- Pyright or mypy for the public interfaces and dataclasses.
- Coverage reporting with an agreed minimum.
- Dependency vulnerability and secret scanning.
- Pre-commit hooks for JSON, whitespace, tests, and secret detection.
- CI on supported Python versions with unit and Docker integration jobs.

Also add tests for paths from a foreign working directory, default handoff with
neighbors, memory limits/corruption, long discussion queries, actual retrieval
score shape, crawler URL filtering, concurrent same-agent memory writes, and
partial failures in concurrent discussion stages.

## Suggested implementation roadmap

### Phase 1: correctness

- Centralize every filesystem path.
- Unify the 512-character query contract.
- Repair score/relevance handling.
- Fix memory concurrency/validation and small control-flow bugs.
- Add regression tests for every fix.

### Phase 2: real integration confidence

- Install the unified environment.
- Start the Docker database.
- Add a miniature Postgres integration fixture.
- Add opt-in Kaggle contract tests.
- Expand `doctor` into a true readiness probe.

### Phase 3: measured performance and quality

- Batch query embeddings and pool DB connections.
- Add per-stage timings and token/tool metrics.
- Tune retrieval against qrels and promote quality thresholds into CI.
- Re-run and version the baseline after every pipeline-affecting change.

### Phase 4: hardening and cleanup

- Protect the Kaggle endpoint and crawler.
- Pin dependencies, models, and container image.
- Consolidate duplicate modules and remove old coursework language.
- Add a final team synthesis artifact.

## Definition of done

The improved system should meet all of these conditions:

- `qubettera doctor` verifies Postgres, the index identity, the embedding model,
  and a real Kaggle request.
- Commands work from any current working directory.
- Every discussion turn records whether it had usable evidence.
- Long round context cannot invalidate the RAG query.
- Retrieval score semantics are consistent and tested.
- The Docker integration and Kaggle contract suites pass.
- Retrieval metrics do not regress below an agreed baseline.
- A multi-agent run produces both an auditable event log and a cited final team
  recommendation.
- Dependencies, model revisions, and the database image are reproducible.
- No arbitrary crawler request can reach local/private infrastructure.

