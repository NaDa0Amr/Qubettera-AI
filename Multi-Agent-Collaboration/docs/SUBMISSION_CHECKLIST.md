# Tasks 1 and 2 Submission Checklist

## Repository

- [ ] `README.md` describes the current task status and commands.
- [ ] The merged Week 2 `src/`, `personas/`, and `prompts/` directories exist.
- [ ] `configs/agent_graph.json` contains the five selected persona IDs.
- [ ] `configs/discussion.json` contains a structured event and three rounds.
- [ ] No `.env`, credential, generated cache, or local virtual environment is committed.

## Task 1

- [ ] Agents are represented as graph nodes.
- [ ] Every edge has a clear source and target.
- [ ] The topology is strongly connected as a directed graph.
- [ ] Recipients and senders can be inspected.
- [ ] Removing an edge blocks that direct route.
- [ ] Invalid and unknown edges are rejected.

## Task 2

- [ ] Every run receives a unique discussion ID.
- [ ] Initial opinions are recorded separately from discussion rounds.
- [ ] Every agent runs once in each of three rounds.
- [ ] Participant order is reproducible.
- [ ] Every round uses the preceding complete snapshot.
- [ ] Routed context is supplied to the correct agent.
- [ ] Each agent uses a stable Week 2 thread across rounds.
- [ ] Every completed turn is logged with round, sender, recipients, and order.
- [ ] A failed run is explicit and retains completed partial history.

## Evidence to show the reviewer

```bash
python -m pytest tests/week3 -q
python -m week3.demo --mode fake
```

Show:

- The graph reports `True` for strong connectivity.
- The demo reports five participants and three rounds.
- The demo reports fifteen discussion turns.
- The generated JSONL log contains one completed turn per agent per round.
- The tests pass.

## Integration before final Week 3 submission

- [ ] Task 3 context logic has been connected and tested with real prior output.
- [ ] Task 4 routing test still passes after integration.
- [ ] Task 5 logs at least one retrieval call per agent per round.
- [ ] Task 6 saves every turn and can reconstruct it by discussion ID.
- [ ] Task 7 returns initial and post-round opinion snapshots.
- [ ] A live end-to-end run uses the Week 2 agents and private `.env` settings.
- [ ] One teammate reviewed the pull request before merging.
