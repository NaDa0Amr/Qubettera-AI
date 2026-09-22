# Reuse of the Merged Week 2 Baseline

The supplied merged Week 2 ZIP is the baseline included in this repository.
Week 3 adds coordination around it.

| Week 2 component | Week 3 use |
| --- | --- |
| `personas/*.json` | Existing identities, stances, priorities, expertise, and retrieval focus become graph participants. |
| `src/personas/loader.py` | Loads and validates the selected persona for every turn. |
| `src/agent/graph.py` | Builds the internal LangGraph workflow used by one agent. |
| `src/agent/state.py` | Holds the agent's messages, persona, neighbor opinions, evidence, queries, and final opinion. |
| `src/agent/checkpoint.py` | Supplies memory support for the Week 2 agent. |
| `src/llm/factory.py` | Preserves the configured LLM provider and model choices. |
| `src/tools/` and `src/retrieval.py` | Preserve internal retrieval, web search, and crawl capabilities. |
| `prompts/` | Preserve persona-aware Week 2 instructions. |
| `week3/week2_adapter.py` | New bridge that gives the Week 3 orchestrator a stable interface to the items above. |

There are two graph concepts:

- `src/agent/graph.py` is one agent's internal execution flow: memory, model,
  tools, and output.
- `week3/agent_graph.py` is the directed communication topology among agents.

The old Week 2 `src/utils/graph_utils.py` constructs an undirected adjacency
list and does not implement the directed strong-connectivity requirement. Task
1 therefore uses the new Week 3 graph module. `personas/debate_graph.json` is
kept as a compatibility copy of the selected topology, while
`configs/agent_graph.json` is the authoritative Week 3 configuration.

The old `src/handoff.get_response()` remains available, but it returns only
text and may create a fresh in-memory checkpointer per call. Task 2 uses
`Week2AgentRuntime`, which keeps one compiled agent graph and checkpointer alive
through the discussion and returns evidence and query metadata as well.

No `.env` file or real credential is included. Copy `.env.example` to `.env`
locally and obtain required values through the team's private channel.
