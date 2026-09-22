# Week 3 Integration Contract

This document fixes the boundaries between the three team workstreams. Agree on
changes here before changing public function signatures.

## Ownership

| Workstream | Tasks | Outputs |
| --- | --- | --- |
| Graph and orchestration | 1 and 2 | `AgentGraph`, `DiscussionOrchestrator`, Week 2 adapter, tests, documentation |
| Context, routing, and retrieval | 3, 4, and 5 | Previous-round context builder, graph-based routing checks, retrieval provider, tests |
| History and opinion evolution | 6 and 7 | PostgreSQL schema/repository, event sink, opinion snapshots, reconstruction queries, tests |

## Shared records

The authoritative records are in `week3/models.py`.

### `DiscussionConfig`

Contains the structured event, ordered participant IDs, round count, and model
configuration. It is validated before a run begins.

### `TurnRequest`

Contains the discussion ID, phase, round, sequence, current agent, direct
recipients, structured brief, routed incoming messages, previous opinion,
retrieval query, and evidence.

### `AgentTurnResult`

Contains the agent's response, explicit current opinion, evidence and retrieval
queries produced inside the Week 2 agent, and runtime metadata.

### `RoutedMessage`

Contains the identifiers, sender, recipients, exact ordering, content, current
opinion, evidence, and timestamp needed by the next round and persistent store.

## Task 3 and 4 connection

The orchestrator currently filters the complete preceding-stage snapshot using
`recipient_ids`. A Task 3/4 implementation may extract that logic into a router
or context builder, but it must preserve these rules:

1. Direct delivery follows the directed edge `sender -> recipient`.
2. Sender and recipient identifiers remain attached to the message.
3. Round N receives messages from the complete snapshot of Round N-1.
4. Current-round output does not leak into another current-round prompt.
5. Removing an edge prevents direct delivery along that edge.

## Task 5 connection

Implement the `RetrievalProvider` protocol in `week3/interfaces.py`:

```python
class TeamRetrievalProvider:
    def build_query(self, request: TurnRequest) -> str:
        ...

    def retrieve(self, query: str, request: TurnRequest) -> tuple[EvidenceItem, ...]:
        ...
```

The provider should build a focused query from the structured topic, the
current agent's retrieval focus, its previous opinion, and messages routed to
that agent. It should not use messages hidden by the graph. For the slide's
acceptance test, return a nonblank query and make one retrieval call for every
agent in every discussion round. Preserve the query, text, title, URL, score,
and useful metadata.

## Task 6 and 7 connection

Implement the `EventSink` protocol in `week3/interfaces.py`:

```python
class PostgresEventSink:
    def write_event(self, event: dict) -> None:
        ...
```

The orchestrator sends these events:

| Event | When | Required use |
| --- | --- | --- |
| `discussion_started` | Before the first agent call | Save run configuration, participants, graph, and start status. |
| `turn_completed` | Immediately after every successful agent turn | Save the message, routing, evidence, opinion, order, and timestamp. |
| `discussion_completed` | After all rounds finish | Mark the run complete. |
| `discussion_failed` | After an execution failure | Mark the run failed and retain completed turns. |

The PostgreSQL implementation should enforce uniqueness of discussion and
message IDs, support ordered reconstruction, and return one discussion-turn row
per agent per round. Initial opinions should remain queryable as phase
`initial`, round 0.

## Integration test checklist

- Replace `DeterministicAgentRuntime` with `Week2AgentRuntime`.
- Replace `NoRetrievalProvider` with the Task 5 provider.
- Combine or replace `JsonlEventSink` with the PostgreSQL event sink.
- Run five initial turns and three discussion rounds.
- Verify 15 discussion-turn rows and 20 opinion snapshots.
- Verify at least 15 discussion-round retrieval events.
- Verify Round 2 prompts contain only permitted Round 1 messages.
- Load the run by discussion ID and reconstruct its ordered history.
