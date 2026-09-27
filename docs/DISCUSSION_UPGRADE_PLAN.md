# Discussion: Current Implementation and Upgrade Plan

Status: implemented. Runtime and regression tests now cover this plan; see README.md for configuration and limits.

## Current implementation

The orchestrator runs independent opening opinions followed by discussion rounds. Each participant sees only messages routed to it from the completed previous round. The standard configuration has five agents and three rounds, producing 20 messages saved to a JSONL event log.

Before each turn, the orchestrator retrieves internal evidence. `Week2AgentRuntime` then invokes a LangGraph agent with a persistent per-agent thread, persona, previous opinion, and neighboring messages. Internal retrieval and web tools are also available inside that graph.

## Planned changes

| Area | Current behavior | Planned behavior |
| --- | --- | --- |
| Query length | Discussion queries allow 1,800 characters; retrieval rejects more than 512. | Build focused queries within 512 characters, reserving space for persona focus and current claims. |
| Retrieval ownership | Orchestrator retrieval overlaps with agent retrieval tools and instructions. | Orchestrator exclusively owns internal RAG; agents may use external web tools as fallback. |
| Retrieval cache | Repeated queries call the backend again. | Cache within each discussion run using normalized query and retrieval settings. Concurrent identical requests share one call; failures are not cached. |
| Citations | Discussion responses have no programmatic citation check. | Check exact `[Source: URL]` citations against evidence actually shown. Retry once, then retain and visibly flag unresolved errors. Update checkpoint memory with the accepted answer. |
| Context limits | Evidence, history, and combined model input can grow too large. | Budget the complete model input, including system prompt, history, tools, repair, and synthesis. Reserve answer space; summarize only when needed and stay bounded if summarization fails. |
| Evidence history | Document fields reset at turn entry, but historical messages and summaries can retain older evidence. | Explicitly track current evidence separately from discussion history; do not treat historical citations as fresh retrieval. Preserve score types. |
| Tool limits | Tool usage is counted across the persistent agent thread. | Reset tool and search limits per discussion turn. |
| Checkpoints | Adapter always defaults to memory despite an existing PostgreSQL factory. | Honor `CHECKPOINT_BACKEND`, keep the connection open for the runtime, close it reliably, and fail clearly on invalid PostgreSQL configuration. |
| Final synthesis | Discussion ends with participant opinions. | Use the same configured LLM in a neutral moderator role to produce one final recommendation with agreements, disagreements, uncertainty, and citations. |
| Legacy modules | Duplicate memory, prompt, search, and graph implementations remain. | Migrate behavior tests, then remove obsolete modules and exports. Preserve `qubettera agent opinion`. |

## Agreed behavior and limits

- The moderator uses no participant persona or retrieval tools. It receives bounded final opinions and deduplicated evidence, prioritizing valid final citations across participants.
- Its final message uses `phase="synthesis"`, sender `moderator`, and all participants as recipients through an explicit broadcast path. Standard runs produce 21 messages.
- Citation checks establish source identity, not whether a source proves a claim. Validation warnings reach neighbors, the moderator, and logs. Evidence-free turns must acknowledge missing support.
- Initial content caps: five evidence items per participant turn, 1,200 characters per excerpt, 6,000 characters per response, 2,000 characters per summary, and ten synthesis evidence items. These remain subordinate to the complete model-input budget; preserve citation URLs when shortening content.
- Cache state ends with the discussion. Retrieval outages yield logged warnings and no fresh evidence; successful empty results may be cached.
- PostgreSQL persists agent threads. Resuming an interrupted whole discussion from the CLI is outside this plan.

## Implementation order and verification

1. Fix query construction, retrieval ownership, caching, and per-turn tool counters.
2. Add complete-input bounds, evidence separation, and citation repair with checkpoint consistency.
3. Wire PostgreSQL lifecycle and the neutral moderator broadcast.
4. Migrate tests, remove legacy modules, and update CLI documentation.

Test concurrent cache hits and failure recovery, 512-character queries, absence of duplicate internal retrieval, bounded input on every model call, citation repair and warning propagation, evidence isolation, PostgreSQL reopen/cleanup, and the final 21-message flow. Run the existing agent/discussion tests and public opinion-command checks before removing legacy code.
