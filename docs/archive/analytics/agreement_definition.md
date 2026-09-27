# Task 2 — Agreement Definition

## What does the agreement score represent?

How aligned or divided the group of agents is **within a single discussion
round**, derived from the individual stance values produced by Task 1.

A high score means the agents held similar opinions that round.  
A low score means the agents were polarised.

---

## What is its range?

`0.0` to `1.0`, continuous.

---

## What does a higher value mean?

The agents' stances were close together — the group was approaching
consensus. `1.0` = all agents had identical stances (zero disagreement).

---

## What does a lower value mean?

The agents' stances were spread across the scale — the group was polarised.
`0.0` = maximum possible polarisation (half the agents at `+1.0`, half at
`-1.0`).

---

## Formula

For each round *r*, collect the stance values of every agent present in that
round into a vector **s**:

```
σ(r) = population standard deviation of s
agreement(r) = 1 − σ(r)
```

Division is implicit: the maximum possible population standard deviation on
the `[-1, +1]` scale is exactly **1.0** (achieved when exactly half the
agents are at `+1` and the other half are at `−1`). Therefore `σ ∈ [0, 1]`
and `agreement = 1 − σ ∈ [0, 1]`.

The **population** standard deviation (denominator *N*, not *N−1*) is used
because we have the full population of participating agents, not a sample
from a larger group.

### Example

```
Round 2
  agent_a =  0.70
  agent_b = -0.60
  agent_c =  0.65

mean   = (0.70 − 0.60 + 0.65) / 3 = 0.25
σ      = sqrt( ((0.70−0.25)² + (−0.60−0.25)² + (0.65−0.25)²) / 3 )
       ≈ 0.561
agreement = 1 − 0.561 = 0.439
```

---

## Why standard deviation instead of mean pairwise difference?

Both are defensible. Standard deviation was chosen for this project because:

1. **Ring topology awareness.** Week 3's discussions use a directed ring graph
   where sub-clusters of agents can form and drift apart without interacting
   directly. Standard deviation captures the full spread of such clusters;
   mean pairwise difference can underestimate polarisation when each cluster
   is internally tight but far from the other (the within-cluster pairs
   all have small differences and pull the mean down).

2. **Interpretability.** `1 − σ` has a direct geometric interpretation: it
   measures how far the opinion distribution is from being a single spike
   (perfect consensus).

3. **Sensitivity to extremes.** Standard deviation is more sensitive than
   the mean pairwise difference when one agent holds a very extreme
   position relative to the rest, which is common in technical debates
   where one "contrarian" expert takes a strong opposing view.

---

## Output field reference

| Field | Type | Description |
|---|---|---|
| `round` | `int` | Discussion round number (0-indexed, as in Task 1). |
| `agreement` | `float` | Agreement score in `[0.0, 1.0]`, rounded to 4 d.p. |
| `n_agents` | `int` | Number of agents whose stances contributed to this round's score. May be less than the total number of participants if an agent has no opinion snapshot for this round. |

---

## How should the value be interpreted across rounds?

A rising `agreement` score across rounds indicates the agents are converging
toward a shared position.  
A falling score indicates the agents are diverging or becoming more polarised.  
A flat score near `0.5` often indicates a stable two-group disagreement
typical of technical debates with a genuine trade-off.

---

## Missing agents

If an agent has no stance snapshot for a particular round (e.g., it did not
speak in that round), that agent is excluded from that round's calculation.
The `n_agents` field reports how many agents actually contributed.

A round with only one agent is given `agreement = 1.0` (vacuous consensus)
and `n_agents = 1`. This is documented here rather than hidden or omitted.

---

## Known limitations

- Agreement is derived from Task 1 stance values, which are LLM-generated.
  Errors in stance scoring (see `docs/stance_definition.md`) propagate into
  the agreement score.
- A single discussion round (round 0 only) produces one agreement score but
  no trend information. Trend analysis requires at least two rounds.
- Standard deviation is symmetric: a round where all agents are at `+0.5`
  looks identical to a round where all agents are at `−0.5`. The agreement
  score does not capture *where* on the scale the consensus is, only *how
  tight* it is. For directional information, see the Task 1 stance values
  and the Task 3 influence scores.
- `agreement = 1.0` does not mean the agents reached a good decision — it
  means they agreed. "Groupthink" and genuine convergence on evidence look
  the same in this metric.

