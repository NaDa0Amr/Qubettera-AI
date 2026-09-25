# Change Log

Recorded 2026-09-25 against baseline commit `e679ff3 using Qwen3`.

This documents the work that moved Qubettera-AI from a MiniLM/384-dim retrieval
stack onto a local **Qwen3-Embedding-0.6B / 1024-dim** stack backed by
PostgreSQL + pgvector, and the nine correctness defects that forensically
analysing recorded live debate runs then surfaced. The work is landed as two
commits:

| Commit | Scope |
|---|---|
| 1 | Pipeline, evaluation, and retrieval foundation |
| 2 | Debate-quality fixes, CLI streaming, and output naming |

---

## 1. Pipeline and evaluation foundation

### 1.1 Embedding model migration

Retrieval now uses `Qwen/Qwen3-Embedding-0.6B` at **1024 dimensions**, replacing
`all-MiniLM-L6-v2`/384. The corpus was rebuilt from scratch: **281 clean
documents / 13,834 indexed chunks / 281 indexed sources**, all carrying the
`Qwen/Qwen3-Embedding-0.6B` identity, so the index and the query embedder are
provably the same model.

`docs/baselines/eval_results.json` and `docs/baselines/collection_report.json`
were regenerated. Collection moved to `curated_plus_discovery`: 110 curated
seeds expanded to 834 discovered sources, 833 fetched successfully, 829 written.

### 1.2 Refreshed evaluation

Strict evaluation (`--require-complete-corpus`, 30 queries, k=5):

| Mode | Hit@5 | MRR | nDCG@5 | Precision@5 | Source recall@5 | Latency |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid | 0.5333 | 0.3917 | 0.3222 | 0.1467 | 0.3667 | 351 ms |
| Hybrid + reranker | 0.4000 | 0.2417 | 0.1895 | 0.0933 | 0.2333 | 410 ms |

Source recall is defined per query over that query's judged sources:
`|retrieved ∩ judged| / |judged|`, averaged over queries. Hybrid-only is the
runtime default and the reranker stays opt-in.

**The reranker is measured worse on every quality metric** and is therefore
disabled by default:

| Delta (rerank − hybrid) | Value |
|---|---:|
| Hit@5 | −0.1333 |
| MRR | −0.1500 |
| nDCG@5 | −0.1327 |
| Precision@5 | −0.0534 |
| Source recall@5 | −0.1334 |
| Latency | +58.5 ms |

Paired bootstrap 95% intervals exclude zero for every quality metric. The
reranker gains a hit on 0 queries and loses hits on 4 (`q25`, `q26`, `q27`,
`q29`). Three causes: `cross-encoder/ms-marco-MiniLM-L-6-v2` is trained on short
MS MARCO web passages rather than scientific text; its `max_seq_length` is 512
tokens while ~13% of `embedding_text` values exceed that and are silently
truncated (p50 310, p90 565, max 1213); and it only sees `max(top_k * 6, 40)`
candidates, so `q22`'s judged paper at rank 43 is unreachable in principle.

### 1.3 Device selection was dead code

`load_embedding_model()` accepted a `device` argument that no caller ever
resolved, so `EMBEDDING_DEVICE` in `.env` had no effect. The embedding stage, the
retrieval embedder, and the reranker now all resolve their device through
`settings.get_embedding_device()`, which returns CUDA when the active torch build
reports it available and falls back to CPU otherwise; an explicit `cuda` request
that cannot be satisfied now fails loudly instead of silently running on CPU.

This is what forced `EMBEDDING_BATCH_SIZE` down to 4 on the 6 GB test GPU: with
the device argument ignored, embedding ran on the GPU anyway while the setting
implied otherwise, and a larger batch produced a CUDA OOM.

### 1.4 Thread-safe model singletons

Retrieval loads the embedder and reranker lazily through cached getters. The
original check-then-act was not thread-safe, so five agents retrieving
concurrently could each load a full copy of the model — the most likely cause of
the CUDA OOM observed during the first live demo. Both getters now use
double-checked locking behind a module-level `_model_lock`, with the construction
factored into `_build_embed_model()` / `_build_reranker()`. `DISCUSSION_MAX_WORKERS`
can therefore be raised without multiplying model memory.

### 1.5 One shared query-length limit

A single 512-character cap existed inside the agent pipeline while the discussion
provider allowed 1,800 characters, so **every round-1+ turn failed with
`retrieval unavailable (query is too long; limit is 512 characters)`** — the
composite debate queries run 1,296–1,622 characters. Both now read the shared
`MAX_QUERY_CHARS` (default 2000) from `qubettera.rag.settings`.

### 1.6 Retrieval contract fixes

- `render_evidence_block` now numbers evidence items **1-based** (`[{index}] {title} | {url}`)
  so the ordinal citations the prompt requests resolve to `evidence[n-1]`.
  Previously the block was unnumbered, which made every `[n]` citation
  unverifiable.
- `TurnRequest` gained `is_final_round`, set by the orchestrator when
  `round_number >= config.num_rounds`. `load_prompt` defaults it to `True` so a
  standalone agent run is still framed as final.
- `build_retrieval_query` truncates with `MAX_QUERY_CHARS` rather than a
  hard-coded `512`.
- `DISCUSSION_TOP_K` (default 5) makes the per-turn evidence budget configurable;
  the debate needs broader context than a single-shot agent answer.

### 1.7 Documentation

`README.md` gained a **PostgreSQL without Docker** section (podman
`pgvector/pgvector:pg17`), a setup rewrite covering `LLM_PROVIDER` and
`EMBEDDING_DEVICE`, and a **Running the live demo** section. `.env.example`
documents the new knobs with comments distinguishing per-turn from lifetime
budgets. `docs/rag/design_decisions.md`, `docs/rag/evaluation_code_review.md`,
`docs/PORTED-CHANGES.md`, and `REVIEW_AND_IMPROVEMENTS.md` were updated to match.

---

## 2. Debate-quality fixes

Each of these was found by reconstructing what a recorded run actually did from
its JSONL event log, not by inspection alone.

### 2.1 Sticky `synthesis_mode` collapsed the debate to one round

**Symptom.** Run `7e2f331a` produced 20 turns but only 5 distinct opinions — each
agent's four turns were identical.

**Cause.** Agents share a checkpointed thread (`thread_id =
{discussion_id}:{agent_id}` with a `MemorySaver`), so any state derived from
`state["messages"]` lives for the whole *agent*, not the *turn*. Once
`synthesis_mode` latched on it was never cleared, so the prompt said "Do NOT call
any tools" for every remaining round.

**Fix.** `system.jinja` was restructured into two independent `{% if %}` blocks so
synthesis styling and the tool mandate are no longer mutually exclusive, and the
`not state.get("retrieved_docs")` clause was removed from the mandatory-retrieval
backstop.

### 2.2 A single tool budget made the web fallback unreachable

**Symptom.** The prompt instructs agents to "use `live_web_search` if the
knowledge base does not return sufficient results", but web search was **never
called** across 24 recorded runs.

**Cause.** `tool_node` gated every tool on one `tool_rounds_used` counter, and
`MAX_TOOL_ROUNDS` defaults to 1. The knowledge-base call consumed the only round
→ `END` → `synthesis_mode=True` → "Do NOT call any tools" → the web was
structurally unreachable. Proven by a live A/B: budget 1 → KB×3, web×0; budget 3
→ KB×3 then web×4.

**Fix.** Web search got its own budget and a **knowledge-base-first ladder**: the
web opens only once the KB round is spent **or** the KB's best hit fell below
`MIN_TOP_SIMILARITY` (0.50). New state fields `kb_rounds_used`,
`web_rounds_used`, `kb_insufficient`, `max_web_rounds`; new env knobs
`MAX_WEB_ROUNDS` and `MAX_WEB_SEARCHES_PER_RUN`. A "round" is one pass of
`tool_node`, so parallel calls in one `AIMessage` share it; availability is
snapshotted before the loop and per-pass flags prevent double-counting.

**Verified.** Run `c9327c62`: web documents **5 → 59**, all 5 agents searching,
20 web docs beyond round 0 (was 0).

### 2.3 A dead retrieval-quality gate

**Symptom.** The gate that was supposed to detect an unhelpful knowledge-base
result never triggered, so agents treated irrelevant evidence as sufficient.

**Fix.** `MIN_TOP_SIMILARITY = 0.50` with `_top_similarity()`, exposing
`top_similarity` and `insufficient` in both retrieval tool envelopes. Measured
effect: the original brief sits at a median top similarity of 0.7185 with 0/20
turns below the gate; `hybrid_architect`'s persona focus alone scores 0.4812 —
below it — confirming the gate can discriminate.

### 2.4 A stale opinion republished verbatim

**Symptom.** A turn could republish the previous round's text byte-for-byte.

**Cause.** `extract_opinion` scanned the entire checkpointed history in reverse,
so an empty turn walked backwards and found the previous turn's opinion.

**Fix.** `extract_opinion` gained keyword-only `since: int | None` and
`allow_history: bool`; `week2_adapter.run_turn` reads `prior_messages` via
`get_state(config)` before `invoke` and calls
`extract_opinion(state, since=prior_messages, allow_history=False)`. A one-shot
"answer directly, no tools" retry was added to `call_model`; if the retry is also
empty the turn **fails loudly** rather than republishing.

### 2.5 Evidence duplication

**Fix.** `_dedupe_evidence` in `orchestrator._run_turn` dedupes on append.
Measured redundancy by round on run `d909c193`: r0 51.7%, r1 31.4%, r2 27.1%,
r3 24.5% (down from 56% before `DISCUSSION_TOP_K`).

### 2.6 Citation instruction drift

**Fix.** `system.jinja` and `opinion.jinja` now give the same bracketed-number /
paper-id instruction, and the evidence heading was changed from
`Evidence {{ loop.index }}\nTitle:` to `[{{ loop.index }}] {{ title }}`. Coverage
check on `d909c193`: **152 numeric `[n]` references, 0 out of range.**

### 2.7 Per-turn budgets were lifetime budgets

**Fix.** `MAX_WEB_SEARCHES_PER_RUN` was being enforced against an agent-lifetime
counter, so an agent that searched early was blocked later. It is now counted per
turn, together with the KB and web round budgets.

### 2.8 CLI streaming and output naming

**New files.** `discussion/console_stream.py` (`ConsoleTurnStream`,
`resolve_persona_names`) prints each completed turn to the terminal with the
persona name, opinion excerpt, query, and evidence count while delegating writes
to the wrapped sink. `discussion/output_naming.py`
(`discussion_log_filename`) produces
`live-5agents-3rounds-<UTC timestamp>-<8-char id>.jsonl`. The objective is
deliberately omitted: it is long, and runs sharing a configuration would differ
only by that text. The full id remains inside the log as `discussion_id`.

`qubettera discuss run` now uses both, and `debug_trace.py` gained budget
reporting plus explicit `⏸️ [KB-First]` / `[Web Budget]` / `[KB Budget]` lines so
a declined tool call no longer reads as an agent simply choosing not to search.

---

## 3. Verification

- **248 tests pass** (`pytest tests -q`, 6.3 s), up from 163 at session start.
- **Mutation testing** — five deliberate mutations, each caught by exactly the
  intended tests; all files restored afterwards.
- **Pylance clean** on every changed file.
- **Live runs**, in order:

| Run | Purpose | Result |
|---|---|---|
| `7e2f331a` | initial live demo, defect discovery | 5 distinct opinions across 20 turns |
| `eb814315` | post-fix forensic analysis | severity of remaining defects quantified |
| `c9327c62` | KB-first ladder verification | web docs 5 → 59, all 5 agents searching |
| `cf5f2afc` | repeat of the same brief | reproduced the results |
| `d909c193` | new serving-stack brief | 421 evidence (200 provider + 206 KB + 15 web) |

`d909c193` reference figures: 0/20 turns below the 0.50 gate (median 0.7185),
152 in-range citations, KB redundancy 51.7% → 24.5% across rounds. Logs remain
in `outputs/discussions/` (gitignored) and are named by run id.

---

## 4. Known open issues

These are **not** fixed by this change set and are recorded so the fixes above
are not overread as a complete solution.

1. **Web search is effectively broken.** On `d909c193`, 24 of 25 DuckDuckGo
   calls returned empty. Reproduced outside the debate: after the first
   `DDGS().text()` call in a process, subsequent calls return `n=0`; a fresh
   client per call succeeds. `agents/search/duckduckgo.py:35` swallows this into
   an empty list, and `search_tool.live_web_search:35` renders it as
   `"No results found for query: ..."`, so **agents cannot tell the provider is
   down** — they conclude the web has no answer. Roughly 44 web documents were
   lost to this in the run above. Two Playwright `Crawl failed` entries are
   unrelated (the browser binary is not installed).
2. **The republished-identical-turn defect still reproduces on non-empty turns.**
   `dr_aris` round 3 on `d909c193` is byte-identical to round 2 (same md5,
   5,119 chars) despite a different query and three different evidence documents.
   Citation misalignment proves the published text was written against round 2's
   evidence: `[5]` ("Jamba-1.5 reduces KV cache 8x") matches round 2's Jamba
   document, not round 3's MoA sparse-attention document. This occurs in **7
   turns across 6 of 24 recorded runs**. The §2.4 guard covers only the empty-turn
   case, and LLM sampling was ruled out (three identical prompts at
   `temperature=0.7` produced three distinct outputs).
3. **Query dilution.** 72–76% of each composite retrieval query is debate
   transcript (recipient messages ~53%, previous opinion ~21%), so the query
   drifts away from the brief. On 11 of 15 measured turns the diluted query and a
   focused query retrieved **0 of 5 overlapping documents**, while the diluted
   query scores a *higher* similarity — diluting the query inflates the gate
   metric while retrieving different documents.
4. **The keyword leg is dead.** `plainto_tsquery` ANDs all terms, and the
   `" | "`-joined composite queries match **zero** chunks: 20/20 turns reported
   `keyword match counts: min=0 max=0`. Hybrid retrieval is vector-only in
   practice, and reciprocal rank fusion degenerates to a single leg.
5. **Unresolved arithmetic error in a live run.** On `d909c193`, `prof_elena`
   reported "4 KiB per token" (~1 GB for 8 requests), dropping the ×32-layers
   factor. The correct figure for Mistral-7B at 32k context is 128 KiB/token, so
   8 concurrent requests need 32 GiB — plus 14 GiB of weights against a 40 GiB
   budget, i.e. **46 GiB, over budget**. `dr_aris` adopted the wrong number in
   rounds 2 and 3, while `systems_specialist` had it right and repeated it nine
   times per round without being heeded. Nothing in the pipeline checks numeric
   self-consistency, so an error of this kind propagates unchallenged.
6. **Fabricated citations.** `systems_specialist` and `hybrid_architect` cited
   `2309.08181` (the vLLM paper) in four turns; that work is **absent from the
   corpus entirely** (0 chunks). `prof_elena` cited `2604.21330` outside her
   turn's evidence.
7. **Corpus domain drift.** ~13% of knowledge-base documents retrieved are
   vision-domain and irrelevant to architecture debates.

### Operational note

The W&B API key in `.env` line 9 appeared in session output and **should be
rotated**. `.env` is gitignored, so no credential is present in either commit.
