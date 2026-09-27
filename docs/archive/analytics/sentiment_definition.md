# Task 4 — Sentiment Definition

## What does the sentiment score represent?

The **emotional tone** of an individual agent's message, independent of the
agent's stance on the discussion proposition.

A high score means the agent wrote with strongly positive, enthusiastic, or
endorsing language. A low score means the agent wrote with critical,
dismissive, or negative language. A score near zero means the message was
factual, descriptive, or evenly balanced.

Sentiment is deliberately distinct from stance. An agent may hold a strongly
positive stance (supporting a proposition) while expressing that position in
neutral, evidence-based prose. Conversely, an agent may hold a neutral stance
while expressing frustration or enthusiasm. Sentiment measures *how* the
message is written, not *what* it argues.

---

## What is its range?

`-1.0` to `+1.0`, continuous, rounded to four decimal places.

| Value | Interpretation |
|---|---|
| `+1.0` | Strongly positive / enthusiastic / endorsing |
| `+0.5` | Moderately positive |
| `0.0` | Neutral / factual / descriptive |
| `-0.5` | Moderately negative / critical |
| `-1.0` | Strongly negative / dismissive |

---

## What does a higher value mean?

The message expresses positive evaluation, enthusiasm, endorsement, or
approval. Example phrasing that tends to score high:

> "Jamba is an ideal fit for these requirements. It excels on long-context
> tasks and is engineered to run comfortably on a single GPU."

---

## What does a lower value mean?

The message expresses criticism, concern, disagreement, or dismissal.
Example phrasing that tends to score low:

> "This approach is fundamentally flawed. The claimed throughput advantages
> do not hold at realistic batch sizes."

---

## Architecture

The sentiment module is one of four independent analytics tasks that feed
the unified analytics engine.

```
Week 3 discussion (JSONL)
        │
        ▼
   loader.py  ──▶  DiscussionLog
        │
        ├──▶ opinion_change.py   (Task 1)  ──▶ stance rows
        ├──▶ agreement.py        (Task 2)  ──▶ per-round agreement
        ├──▶ influence.py        (Task 3)  ──▶ per-agent influence
        │
        └──▶ sentiment.py        (Task 4)  ──▶ per-message sentiment
                    │
                    ▼
              engine.py          (Task 5)  ──▶ unified analytics result
                    │
                    ▼
              report.py          (Task 6)  ──▶ Markdown report
```

`sentiment.py` depends only on `loader.DiscussionLog`. It does not import any
other task module, and no other task module imports it. This keeps the four
analytics tasks independently reworkable, per the package-level design rule.

Internally, the module has three layers:

```
score_sentiment(log)                       # discussion-level entry point
        │
        ▼
SentimentScorer.score_batch(texts, ...)    # batched inference, one model call
        │
        ▼
transformers pipeline (local model)        # lazy-loaded on first use
```

The transformer model is loaded once and reused for every message in every
discussion for the lifetime of the scorer instance.

---

## Input

| Field | Source | Notes |
|---|---|---|
| `log` | `loader.load_discussion(path)` | A `DiscussionLog` containing one `OpinionSnapshot` per agent per round. |
| `snapshot.opinion_text` | From `turn_completed` events in the Week 3 JSONL | The message text to score. The loader's extraction heuristic picks the more substantive of the `opinion` and `content` fields. |
| `snapshot.message_id` | From `turn_completed` events | Used to trace each sentiment score back to its source message. |
| `snapshot.agent_id` | From `turn_completed` events | Sender of the message. |
| `snapshot.round_number` | From `turn_completed` events | Discussion round the message belongs to. |

An optional pre-constructed `SentimentScorer` can be supplied to
`score_sentiment` to reuse a single loaded model across many discussions.
When omitted, a default scorer is created and its model is loaded lazily on
first use.

---

## Method

Each message text is passed through a local transformer classifier that
outputs class probabilities for three classes: `positive`, `neutral`, and
`negative`. The bipolar sentiment score is computed as:

```
sentiment = P(positive) − P(negative)
```

This produces a continuous value in `[-1.0, +1.0]`. Using the difference of
two probabilities (rather than the argmax label) preserves the model's
confidence structure: a message scored `P(pos)=0.9, P(neg)=0.05` yields
`+0.85`, while a message scored `P(pos)=0.5, P(neg)=0.4` yields only `+0.10`
even though both have the same argmax label.

### Why a local transformer and not an LLM call

A per-message LLM call was considered and rejected for this project. The
system is expected to run in production across many discussions and many
messages per discussion, where the cumulative cost and latency of per-message
LLM scoring become impractical. LLM scoring is also nondeterministic even at
temperature 0, which complicates reproducibility. A local transformer runs
deterministically in tens of milliseconds per discussion on CPU, requires no
API key, and produces byte-identical output on repeated runs.

### Why not a lexicon method

Lexicon methods such as VADER and TextBlob have documented accuracy of
roughly 40–47% on technical text. They cannot distinguish descriptive
technical language from emotional tone: a sentence like "This architecture
has significant memory overhead" reads as negative to a lexicon tool because
of the word "overhead," even though it is a neutral factual statement in a
technical debate. This mismatch is fatal for AI architecture discussions
where agents argue from evidence using factual, professional prose.

### Model choice and tiering

The scorer is model-agnostic. It exposes a single `model_name` parameter, and
all downstream behaviour — scoring, aggregation, reporting — is independent
of which model is used.

Two tiers are planned:

- **Tier 1 (prototype).** A general-purpose sentiment model trained on
  developer interactions. Chosen for its availability, small footprint, and
  speed. It is used for the initial integration and testing phase so that a
  working end-to-end pipeline exists sooner.

- **Tier 2 (production, planned).** A model fine-tuned on annotated Week 3
  discussion messages. The Tier 1 model is used as a pre-annotator; human
  annotators correct its labels; the corrected data is used to fine-tune a
  smaller encoder. The interface does not change between tiers — only the
  `model_name` argument.

Switching from Tier 1 to Tier 2 is a one-line configuration change with no
impact on the output schema, aggregation, or report format.

---

## Truncation diagnostics

Week 3 messages routinely exceed 2000 characters, which corresponds to
roughly 500 tokens. The typical transformer default of 512 tokens is
therefore too small: a long message would be silently cut off partway
through, and the model would produce a score based on only the opening
paragraph — potentially missing the sentiment-bearing language that appears
later.

Two design decisions address this:

1. **The default `max_length` is 2048 tokens** rather than the customary
   512. ModernBERT supports up to 8192 tokens, so 2048 stays well within
   the model's architectural range while covering the vast majority of
   Week 3 messages. Callers can override this per scorer or via the CLI.

2. **Every result records a truncation diagnostic.** Two new fields are
   attached to each `SentimentResult`:

   - `token_count` — the number of tokens in the source text *before*
     truncation. Computed by a batched call to the pipeline's tokenizer,
     falling back to a character-based approximation (about 1 token per
     4 characters) when the pipeline does not expose a tokenizer.

   - `truncated` — a boolean, `True` when `token_count > max_length`,
     meaning the model only saw the first `max_length` tokens of the
     message.

The `truncation_summary(results)` helper aggregates these into a single
diagnostic dict:

```
{
    "total_count":       int,     # messages scored
    "truncated_count":   int,     # messages exceeding max_length
    "truncated_share":   float,   # fraction in [0.0, 1.0]
    "sample_message_ids": list[str],
}
```

A message marked `truncated=True` should be interpreted with caution: the
sentiment-bearing language may have been cut off. If truncation is
widespread on a particular discussion, either raise `max_length` further
(up to 8192 for ModernBERT) or split long messages into chunks and average
the scores.

---

## Output

`sentiment.py` exposes three public functions and one aggregation helper.

### `score_sentiment(log, scorer=None) -> list[dict]`

Scores every message in a discussion. Returns one dict per message in the
order the messages appear in the log. Each dict has the following fields:

| Field | Type | Description |
|---|---|---|
| `message_id` | `str` | Week 3 message identifier, e.g. `<discussion_id>:<sequence>`. Empty string if the source event omitted it. |
| `agent_id` | `str` | Sender of the message. |
| `round` | `int` | Discussion round the message belongs to. |
| `sentiment` | `float` | Bipolar score in `[-1.0, +1.0]`, rounded to 4 d.p. |
| `label` | `str` | Argmax class: `"positive"`, `"neutral"`, or `"negative"`. |
| `confidence` | `float` | Probability of the argmax class, in `[0.0, 1.0]`. Low values indicate the model was uncertain between classes. |
| `method` | `str` | Model identifier that produced the score, e.g. `"aieng-lab/ModernBERT-large_sentiment"`. Allows downstream code to distinguish Tier 1 from Tier 2 scores. |
| `text_length` | `int` | Character count of the scored text. |
| `token_count` | `int` | Token count before truncation. Zero for messages that were not scored (empty text). |
| `truncated` | `bool` | `True` when `token_count` exceeds the scorer's `max_length`. |
| `note` | `str \| None` | Populated when the message could not be scored normally. Currently only `"empty_text"` is emitted. `None` for successful scores. |

### `aggregate_by_agent(results) -> dict[str, dict]`

Groups per-message results by `agent_id` and returns:

```
{
    "<agent_id>": {
        "avg_sentiment": float,   # mean sentiment across this agent's messages
        "message_count": int,     # number of messages averaged
    },
    ...
}
```

Messages with a non-`None` `note` (e.g. empty text) are excluded from the
average so that a malformed message cannot skew an agent's aggregate.

### `aggregate_by_round(results) -> dict[int, dict]`

Groups per-message results by round number, returning the same per-bucket
shape as `aggregate_by_agent`. Rounds are returned in ascending order. Noted
messages are excluded, same as above.

### `sentiment_distribution(results) -> dict[str, int]`

Counts messages by label. Always returns all three keys (`positive`,
`neutral`, `negative`) even when a label has zero count, so downstream code
can rely on the shape without null checks.

### `truncation_summary(results, sample_limit=10) -> dict`

Aggregates the per-message truncation diagnostics into a single summary.
The `sample_limit` parameter caps how many truncated message IDs appear in
the `sample_message_ids` field, so the summary stays compact even when
truncation is widespread.

---

## Aggregates

The raw per-message scores are the primary output, but the analytics engine
and Markdown report also consume three aggregates computed from them:

1. **Per-agent average sentiment.** Shows whether particular agents were
   consistently positive, critical, or neutral across the discussion. Useful
   for surfacing persona-level tone differences: a rigorous skeptic and an
   enthusiastic explorer should have measurably different average sentiment.

2. **Per-round average sentiment.** Shows how the group's tone shifted over
   the discussion. A rising trend suggests growing enthusiasm or alignment in
   register; a falling trend suggests growing friction or concern. This is
   distinct from the agreement metric, which measures stance alignment, not
   emotional tone.

3. **Sentiment distribution.** The counts of positive, neutral, and negative
   messages across the whole discussion. A discussion with 90% neutral
   messages is tonally flat and fact-driven; one with a wide positive/negative
   split is emotionally charged. Distribution is a coarse but useful
   summary when the report cannot show every message.

A fourth aggregate — the **truncation summary** — is not a sentiment metric
per se, but is computed alongside them so that downstream consumers know
whether the underlying sentiment scores were produced from complete messages
or from truncated ones.

---

## How to run

All commands assume the repository root is the current working directory
and that the virtual environment is activated.

### Prerequisites

```
pip install -r requirements.txt
```

`requirements.txt` includes `transformers>=4.40.0` and `torch>=2.0.0`.
The first time the scorer runs, HuggingFace downloads the Tier 1 model
weights (~1.6 GB) to the local cache. Subsequent runs load from cache in a
few seconds and require no network access.

### Run on the bundled sample discussions

```
python scripts/run_task4.py
```

The script resolves its input directory in this order:

1. `--dir` if passed explicitly.
2. `WEEK3_OUTPUT_DIR` environment variable.
3. A sibling-repo guess at `../Multi-Agent-Collaboration/outputs/week3`.
4. The bundled `data/sample_discussions/` folder as a fallback.

It writes one JSON file per discussion to `reports/sentiment_<id>.json`.

### Run on a single discussion

```
python scripts/run_task4.py --file data/sample_discussions/425315e8-....jsonl
```

### Run on a custom directory

```
python scripts/run_task4.py --dir ../Multi-Agent-Collaboration/outputs/week3
```

### Override the truncation limit

```
python scripts/run_task4.py --max-length 4096
```

Useful for comparing 512, 2048, and 4096 to see whether the scores change
meaningfully with the ceiling. The default is 2048.

### Run on GPU

```
python scripts/run_task4.py --device 0
```

GPU inference is faster, especially on long messages. Requires CUDA-enabled
`torch`.

### Override the model

```
python scripts/run_task4.py --model path/to/fine-tuned-deberta-v3
```

Used after Tier 2 fine-tuning. No other code changes are required.

### Run the unit tests

```
pytest tests/test_sentiment.py -v
```

All unit tests use a fake pipeline and a fake tokenizer. No model is
downloaded, no network access is required, and the suite completes in under
a second. Expected result: `56 passed`.

### Run the integration tests

```
pytest tests/test_sentiment_integration.py -v -s -m slow
```

The integration tests load the real Tier 1 model and score the actual Week 3
sample discussions. The first run downloads the model; subsequent runs load
from cache. The `-s` flag shows the diagnostic prints (Jamba check, 512-token
truncation count) that would otherwise be suppressed. Expected result:
`27 passed` once the model is cached.

The markers must be registered in `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
markers =
    slow: marks tests that require model download or network access
    integration: marks tests that exercise real models end-to-end
```

### Where outputs land

| Path | Producer |
|---|---|
| `reports/sentiment_<discussion_id>.json` | `run_task4.py` |
| `~/.cache/huggingface/hub/` | HuggingFace model cache (shared across projects) |

The sentiment JSON has the following top-level shape:

```
{
  "discussion_id": str,
  "method": str,
  "max_length": int,
  "message_count": int,
  "messages": [ ... per-message results ... ],
  "by_agent": { agent_id: {avg_sentiment, message_count} },
  "by_round": { round:    {avg_sentiment, message_count} },
  "distribution": { positive, neutral, negative },
  "truncation": { total_count, truncated_count, truncated_share, sample_message_ids }
}
```

---

## Design decisions

### Sentiment is measured, not inferred from stance

Reusing the Task 1 stance score as a sentiment proxy was rejected. Stance
measures agreement with the proposition; sentiment measures emotional tone.
The two are correlated but not identical: an agent that strongly supports a
proposition may express that support with calm, evidence-heavy language and a
near-zero sentiment score. Reporting stance as sentiment would lose that
distinction and would make sentiment redundant with opinion change in the
final report.

### Per-message scoring, not per-agent or per-round

Scores are produced at the message level because that is the only unit the
model can score directly, and because it preserves the ability to aggregate
in any direction. Per-agent and per-round aggregates are computed from the
per-message results rather than scored independently. This guarantees that
every aggregate is consistent with the individual scores that produced it.

### Batched inference, not per-message calls

All messages in a discussion are scored in a single batched forward pass
through the model. On CPU this is roughly ten to fifty times faster than a
loop of single-message calls and produces identical output. The only cost is
a small increase in peak memory, which is negligible for encoder-class
models.

Token counting follows the same pattern: a single batched call to the
tokenizer covers every valid message in the batch, rather than one call per
message.

### Lazy model loading

The `SentimentScorer` class does not import `transformers` or `torch` at
module import time, and it does not load the model in its constructor. The
heavy import and model load happen inside the first call to `score_batch`.
This keeps `import src.analytics` fast and allows the Tasks 1–3 test suite to
run in environments where `transformers` and `torch` are not installed.

### Model output is normalized to a stable vocabulary

Different transformer models use different label schemes (`positive`, `p`,
`LABEL_2`, etc.). The scorer normalizes every model's labels to a single
canonical set of three strings before bucketing probabilities. Adding support
for a new model is a one-line addition to the label map, not a rewrite of the
scoring logic.

### Empty messages receive an explicit neutral result

Messages with empty or whitespace-only text never reach the model. They
receive a neutral result with `note="empty_text"`. This prevents two problems:
the model would produce arbitrary output on an empty input, and aggregations
would include a meaningless score. Aggregate functions skip any result with a
non-`None` note, so empty messages cannot distort per-agent or per-round
averages.

### Default `max_length` is 2048, not 512

The conventional default for sentiment models is 512 tokens, appropriate for
tweets and product reviews. Week 3 messages routinely exceed 2000 characters,
and the sentiment-bearing language often appears after a factual opening
paragraph. A 512-token ceiling would truncate these messages and bias the
scores toward neutral. 2048 covers nearly all Week 3 messages while
remaining well within ModernBERT's architectural range. The truncation
diagnostic makes this decision observable: any message still exceeding 2048
is flagged, so the caller can decide whether to raise the ceiling or chunk
the message.

### Determinism at every layer

There is no sampling, no temperature parameter, and no randomness anywhere in
the sentiment path. Repeated runs on the same input produce byte-identical
output, including token counts and truncation flags. This is a deliberate
contrast with the Task 1 stance scorer, which uses LLM sampling and reports a
median over multiple calls. Sentiment is expected to be a stable reference
signal for the downstream report and dashboard.

---

## Error handling

| Scenario | Handled as | Reason / note |
|---|---|---|
| **Empty message text** | `sentiment=0.0`, `label="neutral"`, `note="empty_text"`, `token_count=0`, `truncated=False` | Never reaches the model or the tokenizer. Excluded from aggregates. |
| **Whitespace-only text** | Same as empty | Treated as empty after stripping. |
| **Model fails to load** | Raises at the first scoring call | The error propagates to the caller; there is no silent fallback because a missing model would invalidate every subsequent score. |
| **Metadata list length mismatch** | Raises `ValueError` | `score_batch` requires that `texts`, `message_ids`, `agent_ids`, and `rounds` are parallel lists of equal length. This is checked before any model work is done. |
| **Unknown model label** | Ignored during normalization | If a model emits a label the map does not recognize, that probability is dropped. If both `positive` and `negative` end up missing, the resulting sentiment is `0.0` and the argmax falls to `neutral`. This is a defensive default, not a normal path. |
| **Missing metadata on individual snapshots** | Empty string / zero | `message_id`, `agent_id`, and `round` default to empty values if the source event omitted them. The result is still produced; traceability is degraded but the pipeline does not fail. |
| **Tokenizer raises an exception** | Falls back to character-based token count | The tokenizer is a diagnostic utility, not a scoring dependency. A broken tokenizer must not fail a scoring call that would otherwise succeed, so `_count_tokens_batch` catches any exception and returns a best-effort approximation. |
| **Pipeline has no tokenizer** | Falls back to character-based token count | The fake pipeline used in unit tests has no tokenizer attribute; the real HuggingFace pipeline does. The fallback keeps both paths working through the same code. |

---

## Known limitations

1. **Domain mismatch in Tier 1.** The prototype model is trained on developer
   interactions (issue trackers, code review comments), not AI architecture
   debates. It may under-detect sentiment in technical advocacy — messages
   that clearly endorse a design choice using factual prose may be scored as
   neutral. Tier 2 fine-tuning is the planned remedy.

2. **Sentiment is not stance.** The metric captures tone, not position. A
   strongly positive score does not imply agreement with the discussion
   proposition, and a negative score does not imply opposition. It should
   never be reported as a substitute for stance.

3. **Argmax label collapses nuance.** The `label` field is a coarse summary.
   The continuous `sentiment` score is the primary metric; `label` is
   provided for aggregation and display. A message with `P(pos)=0.45,
   P(neu)=0.40, P(neg)=0.15` and one with `P(pos)=0.90, P(neu)=0.05,
   P(neg)=0.05` both have label `positive`, but they are very different
   messages.

4. **Truncation at `max_length`.** Messages longer than the configured
   `max_length` (default 2048 tokens) are truncated from the end. The
   `truncated` field flags affected messages so callers can decide whether
   to raise the ceiling or chunk the message. Truncation biases a score
   toward whatever the opening portion of the message expressed, which for
   a technical argument is often the neutral framing rather than the
   evaluative conclusion.

5. **Character-based fallback for token counting is approximate.** When the
   pipeline does not expose a tokenizer, `token_count` is estimated as
   `len(text) // 4`. This is accurate for English prose within about 15% but
   can be off for text with unusual tokenization (very long URLs, chemical
   formulas, code snippets). The `truncated` flag is only as reliable as
   this estimate in the fallback case; the real HuggingFace pipeline always
   uses the true tokenizer.

6. **Short messages are noisy.** Messages shorter than a few tokens may
   produce unstable scores. The `text_length` and `token_count` fields are
   provided so downstream consumers can filter or flag short messages if
   needed.

7. **Cross-tier score comparability is not guaranteed.** A Tier 1 score and
   a Tier 2 score are not on the same scale, even though both lie in
   `[-1.0, +1.0]`. The `method` field records which model produced each
   score; consumers that compare scores across discussions should check that
   all scores come from the same method.

8. **No aspect-level detail.** The module produces one sentiment score per
   message. It does not decompose sentiment by topic or by claim. A message
   that is positive about MoE efficiency and negative about MoE training
   stability receives a single combined score. Aspect-level analysis is out
   of scope for this task.

---

## Planned Tier 2 work

The current implementation is Tier 1. Tier 2 will replace the model behind
the same interface. Planned steps:

1. Use the Tier 1 scorer as a pre-annotator on every message in the Week 3
   sample discussions.
2. Human-correct a stratified sample of those pre-annotations, producing a
   small labeled dataset.
3. Fine-tune a compact encoder on the corrected labels.
4. Evaluate the fine-tuned model against the Tier 1 baseline on a held-out
   split. If the improvement is meaningful, promote the fine-tuned model.
5. Change the `model_name` argument in the default scorer construction. No
   other code changes are required.

The output schema, aggregation logic, error handling, truncation
diagnostics, and report integration remain identical across the two tiers.
```

---

## Summary of changes to the document

| Section | Change |
|---|---|
| New section: Truncation diagnostics | Explains why the default was raised from 512 to 2048, and documents `token_count`, `truncated`, and `truncation_summary` |
| Output → `score_sentiment` fields | Adds `token_count` and `truncated` rows to the fields table |
| Output → new subsection | Documents `truncation_summary` alongside the other helpers |
| Aggregates | Notes that the truncation summary is computed alongside the three sentiment aggregates |
| New section: How to run | Covers prerequisites, all CLI flags, both test suites, marker registration, and the output file shapes |
| Design decisions → new subsection | "Default `max_length` is 2048, not 512" explains the reasoning |
| Design decisions → determinism | Notes that token counts are now part of the deterministic output |
| Error handling | Two new rows: tokenizer raises, pipeline has no tokenizer |
| Known limitations | New limitation #5 on the character-based fallback approximation |
| Planned Tier 2 work | Notes that the truncation diagnostic remains identical across tiers |

The document remains self-contained with no external references, and every field and function it mentions exists in the current code.