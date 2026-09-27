# Task 3 — Influence Definition

## What does the influence score represent?

How strongly each agent's opinion and arguments are **associated with opinion changes in the agents they directly address**, modeled via the **DeGroot (1974) opinion dynamics model**.

A high positive score indicates that when this agent takes a stance, their direct recipients subsequently shift their stances in alignment with that stance.

> **Important distinction:** This metric measures mathematical **association and weight**, NOT absolute proof of psychological causation. An agent's recipients may shift for independent reasons.

---

## What is its range?

`-1.0` to `+1.0`, or `null` (`None`) when insufficient data exists.

---

## What does a higher value mean?

The agent's stance receives a strong positive weight in the fitted DeGroot transition matrix of the agents who receive their messages. Direct recipients systematically moved in direction and proportion to this agent's advocated position.

---

## What does a lower / negative value mean?

A negative weight indicates an inverse association: recipients shifted away from or opposite to the stance advocated by this sender (reactive polarization or counter-advocacy).

`0.0` represents neutral/no measurable association with recipients' subsequent updates.

---

## Mathematical Formulation: The DeGroot Model

In the DeGroot model of opinion dynamics over a communication network, each agent $i$ updates their opinion at round $r+1$ as a linear convex combination of their own prior opinion and the opinions of their in-neighbors (agents who sent messages to $i$):

$$x_i(r+1) = \sum_{j \in \mathcal{N}_i \cup \{i\}} W_{ij} \cdot x_j(r)$$

Where:
* $\mathcal{N}_i$ is the set of agents with directed edges $(j \to i)$ in Week 3's discussion graph.
* $W_{ij}$ is the weight agent $i$ places on agent $j$'s stance.

### Linear System Formulation

For each receiving agent $i$, given $T$ rounds of discussion, there are $T - 1$ round-to-round transitions ($r \to r+1$). We formulate the linear system:

$$A_i \mathbf{w}_i = \mathbf{b}_i$$

Where:
* Row $t$ of $A_i$ contains $[x_k(t)]$ for all $k \in \mathcal{N}_i \cup \{i\}$.
* Element $t$ of $\mathbf{b}_i$ is $x_i(t+1)$.
* $\mathbf{w}_i$ is solved using linear least-squares (`numpy.linalg.lstsq`).

### Aggregation to Sender Influence

For a sender agent $j$, their overall influence score is the average weight assigned to $j$ by all agents $i$ that $j$ directly addresses:

$$\text{influence}(j) = \frac{1}{|\mathcal{R}_j|} \sum_{i \in \mathcal{R}_j} W_{ij}$$

Where $\mathcal{R}_j = \{i \mid (j \to i) \in \text{Edges}\}$ is the set of recipients of agent $j$.

The resulting score is clamped to $[-1.0, +1.0]$.

---

## Output Field Reference

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | Identifier of the sender agent. |
| `influence` | `float \| null` | Estimated influence score in `[-1.0, 1.0]`, or `null` if insufficient data. |
| `condition_number` | `float \| null` | Matrix condition number $\kappa(A)$. High values indicate collinear/stagnant stances. |
| `note` | `str \| null` | Diagnostic explanation if fitting failed or was partially degraded. |

---

## Handling Insufficient Data & Edge Cases

| Scenario | Handled As | Reason / Note |
|---|---|---|
| **Only 1 round (round 0 only)** | `influence = null` | `insufficient_rounds`: At least 2 rounds are required for 1 transition. |
| **Agent has 0 outgoing edges** | `influence = null` | `no_recipients`: The agent did not address anyone in the communication graph. |
| **Fewer transitions than unknown weights** | `influence = null` | `insufficient_data`: Underdetermined linear system. |
| **Collinear stances / zero movement** | `influence = null` | `ill_conditioned`: Condition number $\kappa(A) > 10^6$; fitted weights are numerically unstable. |
| **Some recipient rows failed to fit** | `influence = float` | `partial_fit`: Influence computed from the successfully fitted subset of recipients. |

---

## Known Limitations

1. **Association vs. Causation:** Fitted weights reflect observational regression coefficients, not counterfactual causation.
2. **Topology Dependency:** On static graphs (such as Week 3's fixed ring topology), every agent interacts with the exact same neighbors each round. Dynamic influence routing cannot be disentangled without varied graph structures.
3. **Small Sample Size:** Typical discussions have 4 rounds (3 transitions). While exactly determined for degree-2 nodes, noisy or collinear inputs can cause high condition numbers.

