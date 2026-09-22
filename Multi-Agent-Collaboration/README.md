# Week 3 — Multi-Agent Collaboration

## Discussion Engine & Agent Interaction

## 1. Overview

This week you will transform the individual agents developed in **Week 2** into a functioning **multi-agent discussion system**.

The goal is to build a system in which multiple agents with different personas can interact with one another over multiple rounds, exchange information, retrieve additional knowledge when necessary, and update their opinions as the discussion progresses.

By the end of the week, your system should be capable of running a complete discussion such as:

```text
Topic
  │
  ▼
Initial Agent Opinions
  │
  ▼
Discussion Round 1
  │
  ▼
Discussion Round 2
  │
  ▼
Discussion Round 3
  │
  ▼
Updated Agent Opinions
  │
  ▼
Persisted Discussion History
```

The discussion participants must be connected through a **strongly connected agent graph**, meaning that every agent must be reachable from every other agent through the graph.

The exact graph representation, routing strategy, orchestration architecture, and implementation framework are up to you.

---

# 2. Why This Matters

Week 2 focused on building individual intelligent agents.

An individual agent can:

* represent a persona,
* remember information,
* use tools,
* retrieve knowledge,
* and generate an opinion.

However, the ultimate goal of the platform is to simulate interactions between multiple perspectives.

This week introduces that interaction layer.

The system you build here will become the primary input to **Week 4**, where the resulting discussions will be analyzed for:

* opinion evolution,
* agreement,
* influence,
* sentiment,
* and interaction patterns.

Therefore, the discussion engine must not simply generate text.

It must produce a **structured, persistent record of how agents interacted and how their opinions changed over time**.

---

# 3. The Problem

Build a multi-agent discussion engine capable of coordinating multiple agents around a common topic.

The system must:

1. Load or create multiple agents from Week 2.
2. Connect the agents through a strongly connected graph.
3. Run a multi-round discussion.
4. Route messages according to graph relationships.
5. Allow agents to retrieve additional information during the discussion.
6. Persist the complete discussion history.
7. Track agent opinions over time.
8. Produce a final discussion result that can be consumed by Week 4.

The exact implementation is your responsibility.

---

# 4. What You Need to Build

Your implementation must provide the following capabilities:

### 4.1 Agent graph

Represent the participating agents as a strongly connected graph.

### 4.2 Discussion orchestration

Coordinate multiple rounds of interaction between the agents.

### 4.3 Graph-based routing

Messages must be routed according to the relationships represented by the graph.

### 4.4 Multi-round interaction

The discussion must contain at least three rounds.

### 4.5 Mid-discussion retrieval

Agents must be able to retrieve additional information from the Week 1 knowledge infrastructure during the discussion.

### 4.6 Persistent discussion history

The messages exchanged during the discussion must be persisted.

### 4.7 Opinion evolution

The system must track how each agent's opinion changes throughout the discussion.

### 4.8 Reproducible discussion runs

A discussion should be identifiable and reproducible enough for downstream analysis.

---

# 5. System Overview

Conceptually, your system should implement something similar to:

```text
                         ┌─────────────┐
                         │    Topic    │
                         └──────┬──────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │ Initial Opinions    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Agent Graph       │
                    │                     │
                    │ A ─────► B          │
                    │ ▲       │           │
                    │ │       ▼           │
                    │ D ◄───── C          │
                    └─────────┬───────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
              Discussion            Retrieval
                State               System
                    │                   │
                    └─────────┬─────────┘
                              │
                              ▼
                    Persisted Discussion
                              │
                              ▼
                       Opinion History
```

This is a conceptual model only.

You are **not required to implement this exact architecture**.

---

# 6. Agent Graph

The agents must be represented as a graph.

Each agent is a node.

Relationships between agents are represented as edges.

The graph must be **strongly connected**.

This means that for every pair of agents A and B, there must be a directed path allowing information originating at A to eventually reach B.

For example, this is strongly connected:

```text
A ───► B
▲      │
│      ▼
D ◄─── C
```

because every agent can eventually reach every other agent.

A graph such as:

```text
A ───► B ───► C
```

would not satisfy the requirement because information cannot travel back from C to A.

---

# 7. Graph Requirements

Your implementation must:

* Represent each participating agent as a graph node.
* Represent communication relationships as edges.
* Ensure the graph is strongly connected.
* Use the graph when determining message routing.
* Make the graph configuration inspectable or reproducible.

The graph may be:

* Static.
* Generated dynamically.
* Configured manually.
* Generated from persona characteristics.
* Generated through another justified approach.

The choice is yours.

---

# 8. Graph Design

You should make a deliberate decision about how relationships between agents are determined.

Possible approaches include:

* Manually configured relationships.
* Random graph generation with connectivity constraints.
* Persona-based relationships.
* Similarity-based relationships.
* Weighted relationships.
* Another approach that you can justify.

These are examples, not requirements.

Your documentation should explain:

1. How the graph is created.
2. Why you chose that approach.
3. How strong connectivity is guaranteed.
4. How the graph affects discussion behavior.

---

# 9. Discussion Orchestration

Build a mechanism that coordinates the discussion between the agents.

The system should control:

* Which round is currently running.
* Which agent acts.
* Which messages are available to an agent.
* Which neighboring agents receive a message.
* When retrieval can occur.
* When an agent's opinion is updated.
* When the discussion ends.

The exact orchestration mechanism is up to you.

You may:

* Build your own orchestrator.
* Use a graph-based agent framework.
* Use an existing multi-agent framework.
* Combine multiple approaches.

The framework is not the objective.

The behavior of the resulting discussion system is.

---

# 10. Discussion Rounds

A discussion must contain at least **three rounds**.

A round represents one cycle of interaction in which participating agents produce messages based on the current discussion state.

A conceptual example:

```text
Round 1
    Agent A → Agent B
    Agent B → Agent C
    Agent C → Agent D
    Agent D → Agent A

Round 2
    Agent A → ...
    Agent B → ...
    Agent C → ...
    Agent D → ...

Round 3
    Agent A → ...
    Agent B → ...
    Agent C → ...
    Agent D → ...
```

This is only an example.

Your routing and scheduling mechanism may be different.

---

## Requirements

The discussion system must:

* Support multiple rounds.
* Execute at least three rounds in a complete demonstration.
* Preserve round information.
* Preserve agent identity for each message.
* Preserve the order or sequence of interactions.

---

## Acceptance criterion

A reviewer must be able to inspect a completed discussion and identify:

* The participating agents.
* The discussion topic.
* At least three rounds.
* The messages generated during each round.
* Which agent produced each message.
* Which agent(s) received each message.

---

# 11. Message Routing

Messages must be routed using the agent graph.

Do not simply broadcast every message to every agent unless your graph itself represents a complete communication graph and you can justify why that design is appropriate.

The graph should have a meaningful role in determining communication.

For example:

```text
Agent A
   │
   ├────► Agent B
   │
   └────► Agent D
```

A message generated by Agent A could therefore be delivered to B and D but not directly to C.

The exact routing mechanism is your choice.

---

# 12. Routing Requirements

Your system must:

* Determine message recipients using graph relationships.
* Preserve the sender identity.
* Preserve recipient information where applicable.
* Preserve message ordering.
* Allow agents to respond based on messages they receive.

If your graph uses weighted or typed edges, document what those properties mean.

---

# 13. Agent Context During Discussion

An agent should not generate its discussion response in isolation.

Its response should be informed by the relevant state available to it.

Depending on your architecture, this may include:

* Its persona.
* Its previous memory.
* Messages received from neighboring agents.
* Previous discussion rounds.
* Retrieved knowledge.
* Its current opinion.

You are responsible for determining which information should be included in the agent's context.

Document your reasoning.

---

# 14. Mid-Discussion Retrieval

Agents must be able to access the knowledge infrastructure from Week 1 during the discussion.

This is important because an agent may encounter:

* A claim it wants to verify.
* A topic it needs more information about.
* Evidence that challenges its current position.
* A question raised by another agent.
* Information that could change its opinion.

The discussion engine should therefore allow retrieval to occur **during the discussion**, rather than only before it begins.

---

## Required behavior

At least one agent must demonstrate the ability to:

1. Receive or generate a discussion message.
2. Determine that additional knowledge is useful.
3. Query the Week 1 retrieval system.
4. Receive relevant information.
5. Use that information in a subsequent discussion response.

The exact mechanism is your choice.

---

# 15. Retrieval Strategy During Discussion

You are responsible for deciding when retrieval occurs.

Possible approaches include:

* Agent decides when to retrieve.
* Retrieval occurs when specific conditions are met.
* Retrieval is available as an explicit tool.
* Retrieval occurs at predefined discussion stages.
* Another justified strategy.

The Week 2 agent framework already provides tool/retrieval capabilities.

Your job this week is to make those capabilities function within a **multi-agent interaction**.

---

# 16. Persistent Discussion History

Every discussion run must produce a persistent record of the interaction.

The history should contain enough information to reconstruct what happened.

At minimum, the persisted discussion should identify:

* Discussion/run ID.
* Topic.
* Participating agents.
* Agent personas or identifiers.
* Round number.
* Sender.
* Recipient(s), where applicable.
* Message content.
* Message order or timestamp.
* Retrieval events, where applicable.
* Opinion state/history.

The exact storage format is your choice.

Possible approaches include:

* JSON
* JSONL
* PostgreSQL
* Another database
* Another structured persistence mechanism

Choose an approach that makes downstream analysis practical.

---

# 17. Discussion Run Identity

Each complete discussion should have a unique identifier.

For example:

```text
discussion_id = ...
```

The identifier should allow a downstream system to retrieve the complete discussion history.

Week 4 will use this discussion history as its primary input.

---

# 18. Opinion Evolution

One of the most important outputs of this week is the ability to observe how agents' opinions change.

The system must track each agent's opinion at multiple points during the discussion.

At minimum, capture:

```text
Initial opinion
      ↓
Opinion after Round 1
      ↓
Opinion after Round 2
      ↓
Opinion after Round 3
```

The exact representation is your responsibility.

You may represent opinions using:

* Text.
* Numerical stance values.
* Structured stance representations.
* Embeddings.
* Another defensible representation.

If you use a numerical representation, document what the values mean.

---

# 19. Opinion Update Mechanism

Agents should be capable of changing their opinions based on the discussion.

The system does not require every agent to change its position.

An agent may:

* Strengthen its original position.
* Weaken its position.
* Move toward another position.
* Reject new information.
* Remain unchanged.

What matters is that the system can **observe and record** the state over time.

---

## Acceptance criterion

For a completed discussion, a reviewer must be able to determine:

* Each agent's initial opinion.
* Each agent's opinion at later stages.
* Whether the opinion changed.
* When the change occurred.

---

# 20. Discussion State

Your system should maintain a representation of the current discussion state.

The state may contain:

```text
Topic
Agents
Graph
Current round
Messages
Agent memories
Current opinions
Retrieved evidence
```

This is a conceptual list rather than a required schema.

You should determine which state needs to be persisted and which state can remain transient.

---

# 21. Discussion Termination

The system must have a clear mechanism for determining when a discussion ends.

At minimum, it must support terminating after a configured number of rounds.

For example:

```text
num_rounds = 3
```

You may optionally implement more sophisticated termination conditions.

Examples include:

* Convergence.
* Maximum number of rounds.
* No meaningful opinion change.
* Moderator decision.
* Another condition.

If you implement additional termination logic, document it.

---

# 22. Error Handling

Consider what should happen when:

* An agent fails to respond.
* An LLM request fails.
* Retrieval fails.
* A tool returns an error.
* A message cannot be routed.
* A discussion is interrupted.
* Persistence fails.

You should implement reasonable error handling for the failure modes relevant to your architecture.

Document important decisions.

A failure in one agent should not silently corrupt the entire discussion history.

---

# 23. Reproducibility

A discussion should be reproducible enough for debugging and downstream analysis.

Your system should preserve:

* Discussion configuration.
* Participating agents.
* Graph configuration.
* Number of rounds.
* Relevant model configuration.
* Messages.
* Retrieved evidence.
* Opinion states.

If your system contains stochastic behavior, document any relevant configuration such as:

* Random seeds.
* Sampling parameters.
* Model temperature.
* Other sources of nondeterminism.

Exact reproduction of LLM output is not necessarily required.

The goal is to make the **discussion run and its configuration traceable**.

---

# 24. Constraints

The following requirements are mandatory.

### Required

* A strongly connected agent graph.
* Multiple agents.
* At least three discussion rounds.
* Graph-based message routing.
* Agents capable of accessing Week 1 retrieval during discussion.
* Persistent discussion history.
* Unique discussion/run identification.
* Opinion tracking across multiple rounds.
* Documentation of architecture and major design decisions.
* A reproducible demonstration.

### Not prescribed

The following are intentionally left open:

* Graph representation.
* Graph generation method.
* Graph library.
* Orchestration framework.
* Routing algorithm.
* Message format.
* Persistence technology.
* Opinion representation.
* Opinion update mechanism.
* LLM framework.
* Internal repository structure.

---

# 25. Suggested Repository Structure

The repository intentionally contains minimal scaffolding.

A possible starting structure is:

```text
.
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
│
├── docs/
│   └── .gitkeep
│
├── src/
│   └── .gitkeep
│
├── tests/
│   └── .gitkeep
│
└── outputs/
    └── .gitkeep
```

This is only a starting point.

You may organize the implementation differently.

For example, you may introduce components for:

* graph management
* routing
* orchestration
* discussion state
* persistence
* opinion tracking
* retrieval
* evaluation

You should choose the structure that best fits your architecture.

---

# 26. Testing Requirements

Your implementation should contain tests or reproducible checks for the major system behaviors.

At minimum, demonstrate the following.

## Graph test

Verify that the configured discussion graph is strongly connected.

## Routing test

Verify that messages are delivered according to graph relationships.

## Multi-round test

Verify that the system can execute at least three rounds.

## Retrieval test

Verify that an agent can access the Week 1 retrieval system during a discussion.

## Persistence test

Verify that a completed discussion can be saved and later reconstructed.

## Opinion tracking test

Verify that opinion states are recorded across multiple rounds.

The tests should focus on externally observable behavior rather than specific implementation details.

---

# 27. Acceptance Criteria

The week is considered complete when all of the following are satisfied.

## Agent graph

* [ ] Multiple Week 2 agents can participate in a discussion.
* [ ] Agents are represented as graph nodes.
* [ ] Communication relationships are represented as edges.
* [ ] The graph is strongly connected.
* [ ] The graph configuration is reproducible.

## Discussion engine

* [ ] A discussion can be started for a selected topic.
* [ ] Multiple agents participate.
* [ ] At least three rounds can be executed.
* [ ] Round information is preserved.
* [ ] The discussion can be terminated cleanly.

## Routing

* [ ] Messages are routed according to graph relationships.
* [ ] Sender identity is preserved.
* [ ] Recipient information is preserved where applicable.
* [ ] Message order can be reconstructed.

## Mid-discussion retrieval

* [ ] Agents can access Week 1 retrieval during a discussion.
* [ ] At least one discussion demonstrates mid-discussion retrieval.
* [ ] Retrieved information can influence a subsequent response.
* [ ] Retrieved evidence is associated with the relevant discussion event where practical.

## Persistence

* [ ] Every discussion has a unique identifier.
* [ ] Discussion history is persisted.
* [ ] Messages can be reconstructed in order.
* [ ] Participating agents are identifiable.
* [ ] Discussion configuration is preserved.

## Opinion evolution

* [ ] Initial opinions are recorded.
* [ ] Opinions are recorded at multiple stages.
* [ ] Opinion changes can be identified.
* [ ] The opinion history is associated with the correct agent.

## Reproducibility

* [ ] Setup instructions are complete.
* [ ] Dependencies are documented.
* [ ] Required environment variables are documented.
* [ ] A reviewer can run a complete discussion.
* [ ] A reviewer can inspect the resulting discussion history.

---

# 28. Expected Deliverables

At the end of the week, your repository should contain:

### 1. Multi-agent discussion engine

A working system capable of coordinating multiple agents.

### 2. Agent graph

A strongly connected graph representing communication relationships.

### 3. Multi-round discussion

At least three rounds of interaction.

### 4. Graph-based routing

A working mechanism for routing messages according to the graph.

### 5. Mid-discussion retrieval

Working integration with the Week 1 knowledge infrastructure.

### 6. Persistent discussion history

A structured representation of the completed discussion.

### 7. Opinion history

A record showing how each agent's opinion changes over time.

### 8. Documentation

Architecture, design decisions, setup instructions, and limitations.

### 9. Demonstration

A reproducible example showing a complete discussion from start to finish.

---

# 29. Documentation Requirements

Your documentation should allow another developer to understand how your discussion engine works without reading the entire codebase.

At minimum document:

## Architecture

Explain the major components and their relationships.

## Agent graph

Explain:

* How the graph is represented.
* How it is created.
* How strong connectivity is guaranteed.
* What edges mean.

## Routing

Explain:

* How messages are routed.
* How recipients are selected.
* Whether edges have weights/types.
* How routing affects discussion behavior.

## Orchestration

Explain:

* How rounds are managed.
* How agents are scheduled.
* How discussion state is maintained.
* How termination works.

## Retrieval

Explain:

* How agents access Week 1 retrieval.
* When retrieval occurs.
* How retrieved information enters the discussion.

## Persistence

Explain:

* What is stored.
* Where it is stored.
* How a discussion is identified.
* How a previous discussion can be reconstructed.

## Opinion tracking

Explain:

* How opinions are represented.
* When opinions are recorded.
* How changes are detected.

## Limitations

Document known weaknesses and areas for improvement.

---

# 30. Discussion Output Format

The exact storage format is your choice, but the final discussion output should contain enough information for Week 4 to perform analytics.

Conceptually, the data should be capable of representing:

```text
Discussion
│
├── Topic
├── Participants
├── Graph
│
├── Round 1
│   ├── Message
│   ├── Message
│   └── ...
│
├── Round 2
│   ├── Message
│   ├── Message
│   └── ...
│
├── Round 3
│   ├── Message
│   ├── Message
│   └── ...
│
└── Opinion History
    ├── Agent A
    │   ├── Initial
    │   ├── Round 1
    │   ├── Round 2
    │   └── Round 3
    │
    ├── Agent B
    │   └── ...
    │
    └── ...
```

This is a conceptual data model, not a required schema.

---

# 31. Reviewer Reproduction

Your README must contain exact commands for reproducing the core demonstration.

A reviewer should be able to:

1. Install dependencies.
2. Configure the environment.
3. Connect to the Week 1 and Week 2 components.
4. Load or create the participating agents.
5. Initialize the discussion graph.
6. Start a discussion.
7. Run at least three rounds.
8. Observe messages being routed.
9. Observe at least one retrieval event.
10. Inspect the persisted discussion history.
11. Inspect opinion evolution.

Your actual commands depend on your implementation.

For example:

```bash
# Install dependencies
...

# Configure environment
...

# Start required services
...

# Initialize agents
...

# Start discussion
...

# Run tests
...
```

Replace the placeholders with the actual commands used by your project.

A reviewer should not need to inspect your source code to determine how to run a complete discussion.

---

# 32. Final Demonstration

Your final demonstration should show the complete system operating.

At minimum demonstrate:

### Step 1 — Define the topic

Select a topic supported by the Week 1 knowledge base.

### Step 2 — Load agents

Load at least two agents from the Week 2 framework.

A larger number of agents is encouraged if your implementation can support it.

### Step 3 — Build the graph

Show the communication graph.

Demonstrate that it is strongly connected.

### Step 4 — Start the discussion

Initialize the discussion and record the initial opinions.

### Step 5 — Run Round 1

Show agents exchanging messages according to the graph.

### Step 6 — Run Round 2

Show that agents respond to information received during the previous round.

### Step 7 — Perform retrieval

Demonstrate at least one agent retrieving additional knowledge during the discussion.

### Step 8 — Run Round 3

Show continued interaction after the retrieval event.

### Step 9 — Record final opinions

Show the resulting opinion states.

### Step 10 — Inspect the discussion history

Show that the entire interaction has been persisted and can be reconstructed.

---

# 33. Design Decisions

A major part of this week's work is deciding how multi-agent interaction should actually work.

You should be prepared to justify:

### Why this graph?

Why did you choose your particular graph construction?

### Why this routing strategy?

How does routing influence the discussion?

### Why this orchestration approach?

Why did you choose your framework or custom implementation?

### Why this persistence model?

Why is your representation appropriate for downstream analysis?

### Why this opinion representation?

How can opinion evolution be measured using your representation?

### How does the system scale?

What happens if you increase:

* Number of agents
* Number of edges
* Number of rounds
* Number of simultaneous discussions
* Amount of retrieved context

You do not need to fully solve scalability.

You should identify the limitations of your current design.

---

# 34. Engineering Considerations

The purpose of this week is not to create the most complicated multi-agent framework possible.

Prefer an architecture that is:

* Understandable
* Reproducible
* Testable
* Extensible
* Appropriate for the project
* Able to preserve discussion state
* Suitable for downstream analytics

Be especially careful about separating:

```text
Agent
   │
   ▼
Agent response
   │
   ▼
Discussion engine
   │
   ▼
Routing
   │
   ▼
Other agents
```

The discussion engine should coordinate interaction rather than hiding all interaction logic inside individual agents.

---
# 35. Learning Resources

The following resources support the concepts and implementation tasks in this week. **Required** resources should be studied as part of the week's work; optional resources provide additional explanations, implementation patterns, or alternative approaches.

## Required Resources

### LangGraph Multi-Agent Workflows

**Study time:** ~30 minutes

**Resources:**

https://www.langchain.com/blog/langgraph-multi-agent-workflows

https://academy.langchain.com/courses/intro-to-langgraph

**Relevant to:**

* Building the discussion orchestration engine.
* Understanding graph-based multi-agent workflows.
* Designing the agent communication flow.

This resource directly informs the orchestration engine design using a graph-based multi-agent framework.

---

### LangGraph Concepts and Checkpointing

**Study time:** ~30 minutes

https://www.langchain.com/langgraph

**Relevant to:**

* Understanding LangGraph concepts.
* Persisting discussion state.
* Storing discussion history across rounds.

The resource is particularly relevant to checkpointing and maintaining state throughout multi-round discussions.

---

### Multi-Agent Orchestration from Scratch

**Study time:** ~35 minutes

https://www.channel.tel/blog/multi-agent-systems-orchestration-from-scratch

**Relevant to:**

* Building the orchestration engine.
* Implementing multi-round conversations.
* Understanding orchestration without relying on a framework.

This is especially useful if you choose to implement a custom round-robin orchestration loop instead of LangGraph.

---

## Optional Resources

### Router Knowledge Base Pattern

**Study time:** ~25 minutes

https://docs.langchain.com/oss/python/langchain/multi-agent/router-knowledge-base

**Relevant to:**

* Implementing message routing.
* Designing how agents receive information from other agents.

This provides a concrete routing pattern relevant to the message-routing subtask.

---

### LangGraph vs AutoGen vs CrewAI

**Study time:** ~20 minutes

https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63

**Relevant to:**

* Comparing multi-agent orchestration frameworks.
* Choosing an orchestration framework appropriate for the project's time budget.

This comparison is not necessary if you have already decided to use LangGraph.

---

### LangGraph Tutorial — Arabic Video

**Study time:** ~40 minutes

https://www.youtube.com/watch?v=6i5troGY-q8

**Relevant to:**

* Building the orchestration engine.
* Understanding LangGraph through a bilingual walkthrough.

This supplements the written LangGraph resources.

---

### LangGraph Complete Guide Repository

**Study time:** ~30 minutes

https://github.com/mkassaf/langgraph-complete-guide

**Relevant to:**

* Building the orchestration engine.
* Finding worked examples alongside the official documentation.

This is a reference code repository for additional implementation examples.

---

### Reflection Pattern with Elasticsearch

**Study time:** ~25 minutes

https://www.elastic.co/search-labs/blog/multi-agent-system-llm-agents-elasticsearch-langgraph

**Relevant to:**

* Opinion evolution.
* Influence mechanisms.
* Self-reflection or self-critique patterns.

This is an optional pattern that may be useful if you want richer opinion evolution behavior.

---

### LLM-based Opinion Dynamics

**Study time:** ~20 minutes

https://www.emergentmind.com/topics/llm-based-opinion-dynamics-simulation

**Relevant to:**

* Opinion evolution.
* Influence mechanisms.

This provides conceptual background on opinion dynamics. It is more directly required in Week 4, but the Week 3 source recommends it as useful early context for implementing opinion evolution and influence.

---

## Resource-to-Task Mapping

| Resource                               | Relevant Task(s)                                      | Required? |
| -------------------------------------- | ----------------------------------------------------- | --------- |
| LangGraph Multi-Agent Workflows        | Build orchestration engine                            | Yes       |
| LangGraph Concepts and Checkpointing   | Store discussion history                              | Yes       |
| Multi-Agent Orchestration from Scratch | Build orchestration engine; Multi-round conversations | Yes       |
| Router Knowledge Base Pattern          | Add message routing                                   | Optional  |
| LangGraph vs AutoGen vs CrewAI         | Build orchestration engine                            | Optional  |
| LangGraph Tutorial (Arabic)            | Build orchestration engine                            | Optional  |
| LangGraph Complete Guide Repository    | Build orchestration engine                            | Optional  |
| Reflection Pattern with Elasticsearch  | Opinion evolution and influence                       | Optional  |
| LLM-based Opinion Dynamics             | Opinion evolution and influence                       | Optional  |

---
# 36. Handoff to Week 4

Week 4 will consume the discussion history generated by this week.

The most important handoff is therefore the **structured discussion record**.

Week 4 should be able to obtain a completed discussion and determine:

* Who participated.
* What topic was discussed.
* What the communication graph looked like.
* What each agent said.
* Which round each message belonged to.
* Who communicated with whom.
* What information was retrieved.
* What each agent's opinion was at different points.
* How the discussion progressed.

Document the interface or data format clearly.

At minimum explain:

```text
Input:
    What identifies a discussion?

Output:
    What represents a completed discussion?

Messages:
    How are messages represented?

Rounds:
    How are rounds represented?

Participants:
    How are agents identified?

Graph:
    How is the communication graph represented?

Opinions:
    How is opinion history represented?

Retrieval:
    How are retrieval events represented?
```

The Week 4 analytics engine should be able to consume your discussion output without needing to understand the internal implementation of the discussion engine.

---

# 37. Engineering Mindset

There is intentionally no single correct implementation for this week.

The important distinction is:

```text
Multi-agent system
        ≠
Multiple LLM calls
```

A real discussion engine needs to manage:

```text
Agents
   +
Relationships
   +
Routing
   +
State
   +
Rounds
   +
Knowledge
   +
Opinion evolution
   =
Multi-Agent Discussion
```

Your implementation does not need to implement every possible feature.

It needs to satisfy the required behavior while making reasonable engineering choices.

Think carefully about what information an agent should see, what information the system should remember, and what information must be preserved for downstream analysis.

---

# 38. Definition of Done

You are done when you can demonstrate the following end-to-end flow:

```text
                         Topic
                           │
                           ▼
                  ┌─────────────────┐
                  │  Week 2 Agents  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Strongly        │
                  │ Connected Graph │
                  └────────┬────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Round 1   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Round 2   │
                    └──────┬──────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Mid-discussion  │
                  │ Retrieval       │
                  └────────┬────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Round 3   │
                    └──────┬──────┘
                           │
                  ┌────────┴─────────┐
                  ▼                  ▼
          Opinion History     Discussion History
                  │                  │
                  └────────┬─────────┘
                           ▼
                     Week 4 Analytics
```

At minimum, your final demonstration must show:

* Multiple Week 2 agents.
* A strongly connected communication graph.
* At least three discussion rounds.
* Graph-based message routing.
* At least one mid-discussion retrieval event.
* Persistent discussion history.
* Opinion states across multiple rounds.
* A reproducible discussion run.

Your completed discussion engine will become the foundation for the **analytics and intelligence layer in Week 4**.
