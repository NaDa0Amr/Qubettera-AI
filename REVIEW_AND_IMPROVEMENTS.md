# Qubettera Full Repository Review and Improvement Plan

Review date: 2026-09-22

## Executive summary

The repository now has a sensible unified shape: one installable `qubettera`
package, one CLI, shared resources, a local Qwen3/PostgreSQL RAG subsystem, a
Kaggle-hosted generation model, and a deterministic multi-agent discussion
orchestrator. The automated suite is healthy (`163 passed`). All 19
JSON resource/baseline files parse, and all 11 individual personas validate.

The system is not yet production-ready. The most important remaining problems
are migrated paths that still resolve to old or incorrect locations, a relevance
check that reads a score field the retriever does not produce, and the absence of
real Postgres/Kaggle integration tests.

Several correctness items have since been fixed and validated end to end by a
live five-agent, three-round discussion run: the query-length contract is now
one shared constant, the retrieval model singletons are thread-safe, and the
debate-quality defects found by analyzing a recorded run are resolved (the
tool-round budget and final-round framing are now separate concerns, ordinal
citations resolve against a numbered evidence block, and the per-turn evidence
budget is configurable). The live demo also surfaced the thread-safety defect,
which the unit tests had not covered.

Recommended order:

1. Fix the remaining P0 correctness items below.
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

**FIXED.** The two limits were reconciled onto one shared constant.

Evidence of the original defect (confirmed at runtime by the live demo, where
every round-1+ turn logged `retrieval unavailable (query is too long; limit is
512 characters)`):

- `src/qubettera/discussion/retrieval_provider.py` allowed 1,800 characters.
- `src/qubettera/rag/retrieve.py` rejected anything over 512 characters (a
  MiniLM-era limit; Qwen3-Embedding accepts 32,768 tokens).
- The provider caught that `ValueError` and returned no evidence, allowing the
  discussion to continue as if retrieval merely found nothing.

What changed:

- `MAX_QUERY_CHARS` (default 2,000) now lives in
  `src/qubettera/rag/settings.py` as the single source of truth.
- `_validate_query` enforces it, and both the discussion provider and
  `agents/pipelines/opinion.py` truncate to the same constant, so they cannot
  drift again.
- Regression tests: `test_query_limit_matches_the_discussion_provider_budget`
  and `test_opinion_query_truncation_respects_the_shared_limit`.

Acceptance criterion: every live discussion turn issues a query accepted by
`_validate_query`, or explicitly records why it did not. **Met** - verified
with a worst-case composite query (1,681 characters) that previously failed.

Still open: retrieval status (`ok`, `empty`, `invalid_query`, `unavailable`) is
not yet recorded in turn metadata, so an outage is still only visible in logs.

### 2. Retrieval quality fallback checks a field that is never returned

**FIXED in the discussion path; still open in the agent tool.**

Evidence:

- `src/qubettera/agents/tools/retrieval_tool.py:60-64` treats results as relevant
  whenever `distance` is absent.
- `src/qubettera/rag/retrieve.py` returns `similarity`, `rrf_score`, and
  optionally `text_rank_score`; it does not return `distance`.

Impact: every non-empty retrieval result is accepted, even when similarity is
weak. The intended LLM query rewrite path will only activate for an empty
result set, not for poor matches.

What changed: `TeamRetrievalProvider._to_evidence` now reads the fields
retrieval actually returns, preferring `rerank_score`, then `similarity`, then
`score`. Previously every discussion evidence score was `None`; it now carries
real values (verified live at 0.738-0.794). An existing test had encoded the
bug by asserting `item.score is None`; it now asserts the correct score.

The `retrieval_tool.py` relevance gate is unchanged: choosing a similarity
threshold is a tuning decision, and `distance` (lower is better) is not
comparable to `similarity` (higher is better), so the direction must be fixed
deliberately rather than by assumption.

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

### 3. Retrieval model singletons are not thread-safe (live demo OOM)

**FIXED.** This was the second blocker that prevented the live demo from running.

Evidence (confirmed at runtime):

- The orchestrator retrieves for all agents concurrently through a
  `ThreadPoolExecutor` (`discussion/orchestrator.py:224-225`, sized by
  `DISCUSSION_MAX_WORKERS`, default 5).
- `_get_embed_model()` and `_get_reranker()` in `rag/retrieve.py` did an
  unguarded check-then-act on module globals, so every worker saw a `None`
  cache entry and loaded a full copy of the weights.
- The failed run logged six concurrent `Loading weights: 0%...310` progress
  bars followed by
  `memory allocation failed with OOM on device 0`, after which all five
  agents reported `retrieval unavailable` for round 0.

What changed: both lazy singletons are now guarded by a `threading.Lock`
(`_load_model`). The authoritative state is re-read inside the lock, because
checking a pre-lock snapshot still lets every waiting thread load its own copy
- the first version of this fix had exactly that bug and was caught by
`test_concurrent_model_loaders_share_a_single_instance`, which asserts one
builder invocation across eight racing threads.

A single copy of the embedder plus reranker requires ~1.2 GiB; six concurrent
copies exceeded the 6 GiB GPU.

Related finding: the GPU is shared with the desktop session (~660 MiB), so
concurrency limits and batch sizes must be validated on this machine rather
than on a clean card.

### 4. Several default paths still point to the wrong post-migration locations

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

### 5. The default memory store is not safe enough for concurrent production use

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

### 6. Tool-round budget and final-round framing were the same flag

**FIXED.**

Evidence (measured from a real three-round run,
`outputs/discussions/7e2f331a-73e1-4821-bf46-34eea9f2a089.jsonl`):

- The agent's `messages` list is checkpointed for the whole discussion
  (`week2_adapter.py`, `thread_id = f"{discussion_id}:{agent_id}"` with a
  `MemorySaver`), and round 0 deliberately calls tools via the
  mandatory-retrieval path.
- `call_model` therefore computed `synthesis_mode = tool_count >=
  MAX_TOOL_ROUNDS` from a **lifetime-of-agent** count. After round 0 every
  subsequent turn had `synthesis_mode = True` forever.
- That single `synthesis_mode` flag was then used for two unrelated jobs: loop
  control (refusing further tool calls) and semantic framing ("Synthesize ...
  into your **final** comprehensive persona recommendation now").

Measured consequences:

- Tool-retrieved documents per turn: `20, 15, 13, 5, 15`, then **0 for all 15
  discussion turns** - no round after the initial snapshot ever retrieved.
- `Final Recommendation` headings by round: `r0: 2, r1: 6, r2: 8, r3: 8`. Six of
  fifteen round-1 turns presented themselves as final.
- Late-round stagnation: `systems_specialist` self-similarity r2→r3 `0.938`,
  `hybrid_architect` `0.890`.

What changed:

- `AgentState` gained `tool_rounds_used`, `max_tool_rounds`, and `final_round`.
- `tool_node` increments `tool_rounds_used`; the adapter resets it to `0` at the
  start of every turn, so the budget is genuinely per turn.
- `max_tool_rounds_per_turn()` replaces the inline `os.getenv` read and
  validates the value.
- `call_model` derives `tools_exhausted = tool_rounds_used >= per_turn_budget`
  for loop control only, and passes `final_round` separately.
- `TurnRequest.is_final_round` is computed by the orchestrator as
  `round_number >= config.num_rounds`, so the agent graph never needs to know
  the discussion's round structure.
- `resources/prompts/system.jinja` now contains two **independent** blocks
  rather than one three-way branch: block 1 is the tool policy (mandatory
  retrieval while the per-turn budget is unspent, otherwise no tools), block 2
  is the round framing (final synthesis on the final round, peer response with
  "This is not the final round." otherwise). Keeping the two concerns orthogonal
  means a fresh final round legitimately receives *both* the retrieval
  instruction and the finality framing - the last round is exactly where fresh
  evidence matters most.
- The mandatory-retrieval backstop in `call_model` no longer requires
  `retrieved_docs` to be empty. The discussion adapter pre-fills that list with
  provider evidence on every turn, so the old guard silently disabled the
  backstop for every round after the first - the second, independent reason
  rounds 1-3 gathered no tool evidence. `tool_rounds_used == 0` alone now means
  "this turn has not gathered tool evidence yet". The retry nudge is also
  worded from `final_round`, so it no longer tells a mid-discussion turn to
  produce a final recommendation.
- The `final_round` state default is `True`, because callers that build their
  own graph input (`agents/handoff.py`, `agents/pipelines/opinion.py`) are
  single-shot runs for which the previous final-synthesis wording must not
  change.

Regression tests: `test_spent_tool_budget_on_a_non_final_round_does_not_claim_finality`,
`test_final_round_keeps_the_final_synthesis_framing`,
`test_fresh_turn_still_requires_retrieval_even_on_the_final_round`,
`test_default_final_round_is_true_for_standalone_runs`,
`test_tool_budget_is_reusable_on_a_fresh_turn`,
`test_mid_discussion_turn_keeps_a_fresh_tool_budget_across_rounds`,
`test_only_the_final_round_is_marked_final`,
`test_mandatory_retrieval_backstop_fires_when_evidence_was_prefilled`.

Related and still open:

- P0 #2 - the `distance` relevance gate in `agents/tools/retrieval_tool.py` is
  dead in production (0 of 188 evidence items carried a non-null `distance`), so
  the LLM query-regeneration fallback never fires. Fixing it requires a
  calibrated threshold on `similarity`/`rerank_score`, which is a tuning
  decision rather than a correctness fix.
- Evidence items from the discussion provider (cosine, ~0.6-0.8), the
  `knowledge_retrieval` tool (RRF, ~0.01-0.03), and `live_web_search` (`None`)
  arrive on three incompatible score scales. No consumer sorts by `score` today,
  so the defect is latent.

### 7. Ordinal citations had no referent in the evidence block

**FIXED.**

Evidence: `hybrid_architect` and `grad_student` cite by ordinal (`[1]`, `[[2]]`)
while the other three personas cite full URLs. `render_evidence_block` emitted
an unnumbered bulleted list, so a bracketed ordinal resolved to nothing - the
numbers matched neither evidence position nor tool-call rank (for example
`grad_student` round 0 cited `[[2]]` for "VRAM" while the only matching evidence
sat at position 6). All 18 URL-style turns did resolve, so no URL was
fabricated.

What changed: `render_evidence_block` numbers items 1-based in tuple order, so
`[n]` now resolves to `evidence[n-1]`. Regression test:
`test_render_evidence_block_numbers_items_in_order`.

### 8. The discussion evidence budget was fixed at five items

**FIXED.**

`DEFAULT_TOP_K = 5` was hard-coded, and `TeamRetrievalProvider()` was
constructed with no arguments in both `cli.py` and `discussion/demo.py`, so the
per-turn evidence depth could not be changed without editing source. The setting
now reads `DISCUSSION_TOP_K` (default `5`) with validation, and the constructor
still accepts an explicit `top_k` that takes precedence. Regression tests:
`test_top_k_defaults_to_five_and_is_configurable`,
`test_top_k_env_is_validated`, `test_configured_top_k_is_used_for_retrieval`.

## P1: high-value improvements

### 9. `retrieve_batch` does not batch and every turn opens a new DB connection

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

### 10. Retrieval quality needs another tuning cycle

The stored complete baseline contains 13,834 chunks and 281 sources. At `k=5`:

| Mode | Hit@5 | Precision@5 | MRR | nDCG@5 | Source recall | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid | 0.5333 | 0.1467 | 0.3917 | 0.3222 | 0.3667 | 351.36 ms |
| Hybrid + rerank | 0.4000 | 0.0933 | 0.2417 | 0.1895 | 0.2333 | 409.89 ms |

The reranker lowers every reported quality metric, so keeping reranking disabled
by default is correct. The paired comparison now makes this statistically
explicit: reranking gains a hit on 0 of 30 queries and loses hits on 4, and the
bootstrap 95% intervals exclude zero for Hit@5, MRR, nDCG@5, precision, and
recall. Retaining the current `ms-marco-MiniLM-L-6-v2` reranker is a real loss
rather than noise; it would need to be replaced with a scientific-domain model
to be worth enabling.

Note that absolute Hit@5 understates retrieval quality here: the same queries at
`top_k=50` find a judged paper for 29/30 queries at a median rank of 4. See
`docs/rag/evaluation_code_review.md` for the full interpretation.

Recommended experiments:

- Inspect failures per query before changing algorithms.
- Measure actual tokenizer truncation for 1,200-character chunks plus contextual
  prefixes. The reranker truncates ~13% of candidate texts at its 512-token
  limit, and only 40 candidates reach it.
- Tune chunk size/overlap, RRF `k`, candidate pool, and source limits through a
  small grid search.
- Compare PostgreSQL full-text configurations for technical terms, acronyms,
  model names, and hyphenated tokens.
- Expand qrels beyond source-level matching to passage-level relevance, and
  admit topically-equivalent recent papers so the metric measures answer
  correctness rather than historical-citation matching.
- Re-baseline against a fixed corpus snapshot so model changes are measurable
  without the corpus-recency confound.
- Add a minimum quality gate so regressions fail CI.

### 11. `doctor` checks construction, not real service health

`src/qubettera/cli.py:102-119` validates the index with a database query but only
constructs the generation client. A dead, expired, or incompatible Kaggle
tunnel may still be reported as healthy.

Recommended change:

- Check the configured Kaggle endpoint with a low-cost model-list or minimal
  generation request and a short timeout.
- Validate model name, context setting, authentication, and tool-calling support.
- Report dependency availability separately from endpoint availability.
- Add `--offline` and `--json` modes for CI and automation.

### 12. Live integration contracts are untested

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

### 13. Remote endpoint and crawler hardening

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

### 14. Pin runtime and model identities for reproducibility

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

### 15. Remove duplicate and legacy code paths

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

### 16. Fix smaller control-flow edge cases

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

### 17. Improve failure policy and observability

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

### 18. Add a final team synthesis stage

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

### 19. Add engineering quality gates

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
- ~~Unify the 512-character query contract.~~ Done: one shared `MAX_QUERY_CHARS`.
- Repair score/relevance handling. (Discussion path done; agent tool open.)
- ~~Make the retrieval model singletons thread-safe.~~ Done: validated by the
  live demo, which previously OOM'd on five concurrent model loads.
- ~~Separate the tool-round budget from final-round framing.~~ Done: the budget
  is per turn, only the last round is framed as final, ordinal citations resolve
  against a numbered evidence block, and per-turn evidence depth is configurable
  through `DISCUSSION_TOP_K`.
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

