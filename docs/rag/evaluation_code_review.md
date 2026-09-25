# Repository Readiness Review

Reviewed: 2026-09-01

## Outcome

The repository is ready as a reproducible local RAG/retrieval prototype. The
pipeline completes with strict corpus coverage, publishes its PostgreSQL index
atomically, validates artifact/model identity, resumes embedding safely, and
has a passing regression suite.

This is not yet a production service: it has no HTTP API, authentication,
background scheduler, monitoring, or deployment manifest. Those are product
deployment concerns rather than correctness gaps in the current CLI pipeline.

## Verified baseline

Refreshed 2026-09-25 after migrating embeddings from `all-MiniLM-L6-v2`/384 to
`Qwen/Qwen3-Embedding-0.6B`/1024 and rebuilding the corpus:

| Check | Result |
|---|---:|
| Clean documents | 281 |
| Indexed chunks | 13,834 |
| Indexed sources | 281 |
| Judged-source coverage | 24/24 |
| Fully covered evaluation queries | 30/30 |
| Test suite | 143 passed |

Latest strict evaluation (`--require-complete-corpus`, 30 queries, k=5):

| Mode | Hit@5 | MRR | nDCG@5 | Precision@5 | Source recall@5 | Latency |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid | 0.5333 | 0.3917 | 0.3222 | 0.1467 | 0.3667 | 351 ms |
| Hybrid + reranker | 0.4000 | 0.2417 | 0.1895 | 0.0933 | 0.2333 | 410 ms |

Hybrid-only retrieval is the runtime default (`--rerank` is opt-in). Reranking
remains available for experiments and is always measured as an ablation. The
reranker is a MiniLM cross-encoder, so reranking quality is not improved by the
Qwen3 migration.

The previous MiniLM baseline scored Hit@5 `0.6000`, MRR `0.3522`, nDCG@5
`0.2808`, precision `0.1400`, and source recall `0.3500` on a 15,162-chunk /
297-source corpus. Qwen3 improves MRR, nDCG@5, precision, and source recall, and
lowers Hit@5 from `0.6000` to `0.5333`. Treat this as a ranking-quality
improvement rather than a clean model-only comparison: the corpus was rebuilt at
a different time, so chunk and source counts differ.

### Reading these numbers

Hit@5 `0.5333` understates retrieval quality, for reasons that are properties of
the test set rather than of the retriever:

- **Judged papers are usually retrieved, just below rank 5.** Re-running the same
  queries at `top_k=50` finds a judged paper for **29/30 queries (96.7%)**, at a
  median rank of **4**; 22/30 are within the top 10. Hybrid `Hit@5` only counts
  rank ≤ 5.
- **The judgments are source-level and historical.** Each query has exactly two
  relevant sources (24 distinct papers), and they are the seminal papers
  (`1701.06538` MoE, `2004.05150` Longformer, `1904.10509` Sparse Transformer,
  `2405.21060` Mamba-2). The corpus is meanwhile dominated by recent arXiv
  preprints, some titled after the query wording itself. The 14 "misses" return
  topically correct papers, so the metric measures *"was the seminal paper
  retrieved"* rather than *"was the answer correct"*.
- **`Precision@5` is bounded at 0.40 by construction.** With two relevant
  sources and `FINAL_SOURCE_LIMIT = 1` (at most one chunk per source in the
  output), at most 2 of 5 slots can ever be relevant. The observed `0.1467` is
  ~37% of that ceiling, not 15% of a ceiling of 1.
- **The reranker materially hurts ranking.** Paired bootstrap 95% intervals
  over the 30 queries exclude zero for every quality metric (Hit@5
  `[-0.2667, -0.0333]`, MRR `[-0.2417, -0.0667]`, nDCG@5 `[-0.1927, -0.0762]`).
  Per query, reranking gains a hit on **0** queries and loses hits on **4**
  (`q25`, `q26`, `q27`, `q29`). Three contributing causes: the reranker is
  trained on short MS MARCO web passages rather than scientific text; its
  `max_seq_length` is **512 tokens** while ~13% of `embedding_text` values
  exceed that (p50 310, p90 565, max 1213) and are silently truncated; and
  reranking only sees `max(top_k * 6, 40)` candidates, so `q22`'s judged paper at
  rank 43 is unreachable in principle.

Consequently the Hit@5 gap versus the MiniLM baseline is most likely a
corpus-recency artifact rather than a Qwen3 regression: MRR, nDCG@5, precision,
and source recall all improve, and the two runs used differently-dated corpora.

### Latency measurement caveat

Two consecutive strict runs produced identical quality metrics but very
different rerank latency (1699 ms versus 410 ms average; the hybrid mode stayed
at 345/351 ms). The cause is not definitively established; the likely
contributors are first-call CUDA initialization in the earlier run and GPU
contention, since the 6 GB device is shared with the desktop. Treat the quality
metrics as reproducible and the reranked latency figure as environment-sensitive.

## Readiness improvements completed

- Collection rejects ar5iv conversion shells and falls back to PDF extraction.
- Quality-aware merging replaces broken persisted records while preserving
  healthy existing documents.
- Curated sources cover every fixed qrel; the stale Hugging Face Mamba URL was
  replaced with the maintained Falcon Mamba article.
- Cleaning output and chunk output use atomic JSONL replacement.
- Chunking fails clearly when no usable chunks are produced.
- Embedding cache reuse requires model, revision, dimension, preprocessing,
  pipeline, and content identity.
- Reused vectors receive current chunk metadata, preventing stale document
  indexes and timestamps from leaking through the cache.
- Storage rejects missing fields, duplicate IDs/hashes, incompatible artifact
  identities, dimension mismatches, and non-finite vectors.
- Database configuration is shared and reports missing environment variables
  clearly.
- Retrieval validates queries, candidate limits, query-vector dimensions, and
  reranker output length.
- Evaluation uses exact normalized source qrels, fixed-IDCG nDCG, source-level
  deduplication, coverage gates, run manifests, and paired reranker comparison.
- Console output is safe on legacy Windows encodings.
- Direct execution (`python src/<stage>.py`) is covered by tests.

## Remaining engineering risks

1. Contextual chunks no longer risk truncation: `Qwen/Qwen3-Embedding-0.6B`
   accepts 32768 tokens, far above this corpus's chunk sizes, so the former
   MiniLM 256-token constraint is retired. Chunking remains an evaluated
   tuning knob rather than a truncation workaround.
2. The 30-query evaluation is suitable for regressions but too small for broad
   statistical claims or domain-general conclusions. Its two-source,
   seminal-paper judgment style also rewards historical-citation matching over
   answer correctness, so absolute Hit@5 should not be read as end-user
   retrieval quality (see "Reading these numbers" above).
3. The reranker's 512-token limit truncates ~13% of candidate
   `embedding_text` values, and its 40-candidate pool bounds what it can
   rescue. A scientific-domain reranker would be needed before enabling it by
   default.
4. Static discovery has limited coverage for JavaScript-rendered blog indexes.
5. `plainto_tsquery` and English stemming remain imperfect for rare acronyms.
6. Collection depends on external services and can be slow or rate-limited;
   existing artifacts allow downstream stages to run independently.

## Reproduction

```powershell
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Edit PostgreSQL credentials in .env

python src\run_pipeline.py
python src\evaluate.py --require-complete-corpus
python -m pytest tests -q -p no:cacheprovider
python -m compileall -q src tests
```

For a rebuild that preserves the current raw collection:

```powershell
python src\run_pipeline.py --skip-collection
```
