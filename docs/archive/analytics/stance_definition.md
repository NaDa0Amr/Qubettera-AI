# Task 1 — Stance Definition

## What does the stance value represent?
How strongly an agent's opinion, at a given round, supports or opposes the
discussion's proposition — the recommendation implied by the Week 3
discussion's stated `objective` and `topics` (see `DiscussionLog.proposition()`
in `loader.py`).

## What is its range?
`-1.0` to `+1.0`, continuous.

## What does a higher value mean?
Stronger support for the proposition. `+1.0` = strongly in favor.

## What does a lower value mean?
Stronger opposition. `-1.0` = strongly opposed. `0.0` = neutral, undecided,
or evenly weighing both sides with no lean.

## How is an opinion converted into the value?
An LLM call (`StanceScorer.score`) is given:
1. The fixed proposition (same string for every round/agent in a discussion).
2. The agent's raw opinion text for that round. This is normally Week 3's
   `turn_completed.message.opinion` field, but `loader._extract_opinion_text`
   falls back to `message.content` if `opinion` looks like a short
   placeholder/header rather than the real argument (some Week 3 runs leave
   `opinion` truthy-but-trivial, which previously caused every round to
   score as 0.0 "no substantive opinion").

Each opinion is actually scored `num_samples` times (default 3), each an
independent call at temperature 0, and the reported stance is the **median**
of those samples (`_median_result` in `stance_scorer.py`). This exists
because a single call can simply misjudge a long, technical opinion: on a
real discussion, one call scored an agent's explicitly pro-MoE-hybrid
message as strongly anti-MoE, while the same agent's other rounds — and the
message's own text — were consistently pro-hybrid. Taking the median of 3
samples means one such outlier gets outvoted rather than trusted outright.
The `reasoning` reported alongside the median stance comes from whichever
sample's stance is closest to the median, so it's a real justification the
model gave, not a synthesized sentence. All individual samples are kept on
`StanceResult.samples` (and surfaced as `stance_samples` in each output
row) so a wide spread across samples remains visible even though only the
median is reported as "the" stance.

It returns a single float plus a one-sentence justification, at temperature 0
for reproducibility. Mixed opinions ("supports X but concerned about Y") are
scored as reduced-magnitude support/opposition rather than forced to 0 — see
`STANCE_SYSTEM_PROMPT` in `stance_scorer.py`.

This was chosen over an embedding-similarity approach because the discussion
proposition here is multi-faceted (architecture choice + several sub-topics),
and a single embedding axis tends to lose the "supports X, concerned about Y"
structure that shows up throughout these discussions. An LLM scored directly
against the stated proposition handles that nuance and keeps every round
anchored to the same reference point, which is the failure mode called out
in the assignment (comparing round N to round N+1 only means something if
both were scored against the same thing).

## How should the value be interpreted across rounds?
Each `(agent_id, round)` pair gets its own independent stance call, always
against the same proposition string for that discussion. `change` is
`stance(round_n) - stance(round_{n-1})` per agent; it is `None` (null) on an
agent's first recorded round, since there is no prior round to compare
against. A sustained positive `change` sequence means the agent is moving
toward stronger support; sustained negative means moving toward opposition.

## How the proposition itself is built
`DiscussionLog.proposition()` first looks for a topic phrased as an
"`<A>` versus `<B>`" debate (Week 3's topics are usually written this way,
e.g. "Dense feed-forward layers versus sparse Mixture-of-Experts layers.").
If found, it's rewritten into a real for/against claim: "This team should
use `<B>` rather than `<A>`." Only then is the claim something an agent can
actually agree or disagree with.

This matters because the objective alone ("Recommend a Transformer
architecture...") is a task description, not a claim — any agent who gives
*any* confident, well-justified recommendation "fulfills" it, so early
versions of this scorer put nearly every agent near +1.0 regardless of
whether they argued for a dense or a sparse/MoE design, hiding genuine
disagreement between agents. Deriving a bipolar claim from the topics fixes
that for the primary debated axis.

If no topic matches the "versus"/"vs" pattern, `proposition()` falls back to
the old `objective + topic summary` format, which still anchors every round
to the same string but won't distinguish agents who disagree on substance
while both answering the open-ended objective confidently.

## Known limitations
- Stance is model-generated; even with median-of-3 sampling, an unusually
  bad model or a genuinely ambiguous opinion can still produce a misleading
  score. A wide spread across `stance_samples` for a row is a signal to
  spot-check that row's `reasoning` before trusting it.
- Sampling 3x instead of once means Task 1 now costs ~3x the LLM calls per
  discussion. `StanceScorer(num_samples=1)` restores the old single-call
  behavior if that cost isn't worth it for a given run.
- Temperature is kept at 0 for every sample rather than raised to induce
  deliberate diversity; the 3 samples mainly guard against a single call's
  misjudgment and against any backend-level non-determinism (some hosted
  MoE-routed models are not perfectly deterministic even at temperature 0).
  If a provider is fully deterministic at temperature 0, all 3 samples will
  simply agree and the median is a no-op safety margin, not a source of
  diversity.
- Only the *first* "versus"/"vs" topic is used to build the proposition, so
  a discussion debated across several axes (dense-vs-MoE, layer count, model
  dimension) is currently scored only on the first axis found. Additional
  axes are visible in the topic list but not separately scored.
- If a discussion's topics don't contain an explicit "versus"/"vs" framing,
  the proposition falls back to the task-description form, which inherits
  the ceiling-saturation issue described above.
- This is a stance measurement, not a causal claim — it says where an agent
  stood, not why it moved there (see Task 3 for influence).