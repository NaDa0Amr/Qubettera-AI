# Week 2 Battle Plan — Revised

*Same 2-day, 2-person structure as the original plan, with fixes applied inline. Notes mark what changed and why — flag these to your teammate before you split up so you're not discovering the changes mid-build.*

---

## 1. The High-Level Blueprint (Source of Truth)

- **Framework**: `LangGraph`
- **LLM Gateway**: **OpenRouter**
- **Topology**: **ReAct Agent (tool-calling)** + **Sequential Opinion Graph**
- **Integration**: Week 1's `retrieve()` wrapped as a LangChain `@tool`

> **📝 Note — checkpointer name unverified.** The original plan says `MemorySaver` in one place and `InMemorySaver` in another. Don't guess — whoever writes `graph.py` should check the current LangGraph docs for the real class name *before* writing the code, since this is exactly the kind of thing that silently changes between framework versions. Five minutes now saves a debugging session later.

> **📝 Note — don't copy Week 1's whole `src/` folder.** The assignment explicitly says not to duplicate the Week 1 ingestion pipeline, and you don't need `collection.py`, `clean.py`, `chunk.py`, or `store.py` at runtime — only `retrieve.py` and its direct dependencies (DB config, embedding model, reranker). Copy just what's needed, or `pip install -e` Week 1 as a local package if time allows. Keeping one source of truth for retrieval also means a later Week 1 bugfix doesn't leave you with two diverging copies.

---

## 2. Before You Split Up (15 minutes, both people)

> **📝 Note — new step, not in the original plan.** Person A designs `AgentState`; Person B designs the persona schema. If these are built independently and only reconciled at end-of-Day-1 merge, you'll spend your least-slack hours fixing shape mismatches instead of building. Fifteen minutes now avoids that.

Agree together on:
- The `AgentState` TypedDict shape (messages, persona, retrieved_docs, memory_summary — whatever fields you actually need).
- The persona JSON shape (see §3 below — this needs one extra field vs. the original plan).
- What the retrieval tool's output looks like once it lands in state (so Person A can write `call_model` without waiting on Person B's tool wrapper).

---

## 3. Persona Schema — Revised

> **📝 Note — this is the one required fix.** The assignment states: *"Do not hard-code behavior for the individual personas in a way that prevents the framework from supporting new personas."* The original plan's "Hack 1" (see §6) branches on persona *name* inside the graph code (`if persona == "Pro-Efficiency": ... elif "Pro-Reliability": ...`) — that's exactly the hardcoding the spec prohibits, and it breaks the moment you add a third persona. The fix is cheap: move the retrieval-focus instruction into the persona config itself.

```json
{
  "name": "Dr. Efficient",
  "background": "Cloud Architect",
  "stance": "pro-MoE/SSM",
  "style": "...",
  "priorities": "FLOPs and memory bandwidth",
  "retrieval_focus": "advantages, scaling laws, efficiency benchmarks, FLOPs, memory bandwidth"
}
```
```json
{
  "name": "Dr. Reliable",
  "background": "AI Safety Researcher",
  "stance": "pro-Dense/Sliding Window",
  "style": "...",
  "priorities": "deterministic behavior and routing stability",
  "retrieval_focus": "routing instability, load-balancing failures, quality degradation"
}
```

The single new field (`retrieval_focus`) replaces the branching logic entirely — `call_model` just reads it off whatever persona object it's given, with no knowledge of how many personas exist or what they're called.

---

## 4. Timeline: 2 Days, 2 Persons

### Day 1: Foundation & Core Loop
*Goal: a working ReAct agent that can talk, retrieve, and remember.*

**Person A (Backend / Graph Engineer)**
1. *(30 min)* Set up the Week 2 repo. Copy/wrap only `retrieve.py` + dependencies from Week 1 (see note in §1) so you can `from src.retrieve import retrieve`.
2. *(1 hr)* Write `src/agent/state.py` — the `AgentState` you agreed on in §2.
3. *(2 hrs)* Build the LangGraph graph in `src/agent/graph.py`. `call_model` node, `tool_node`, conditional edges (tool call → loop; else → END). Use the confirmed checkpointer class name from §1.
4. *(1 hr)* Write `src/tools/retrieval_tool.py` — wraps `retrieve()`, formats output with URLs for citation.
5. *(1.5 hrs)* Wire up the checkpointer and a basic `run_agent.py` (`thread_id` + prompt in, response out).

> **📝 Note — assign the context-overflow mitigation or explicitly descope it.** The original plan lists "trim messages, keep a summary string" as a risk mitigation (§7 below) but never assigns it as a task, which means it silently doesn't get built. Either give Person A ~30-45 extra minutes here to add a basic `trim_messages` step to the graph, or decide now you're skipping it and say so plainly in the README's Limitations section — the assignment explicitly wants documented limitations, so "we didn't build this, here's why" is a legitimate answer. Just don't let it fall through unowned.

**Person B (Personas / Prompting / Data)**
1. *(30 min)* Write `personas/schema.json` — the revised schema from §3 (includes `retrieval_focus`, not persona-name branching).
2. *(2 hrs)* Create 2 distinct personas (Dr. Efficient / Dr. Reliable, from §3).
3. *(1 hr)* Write system prompt templates in `prompts/system.jinja`. Have the prompt read `persona.retrieval_focus` generically — no persona-specific conditionals in the prompt logic either.
4. *(1.5 hrs)* Set up `src/llm/client.py` (OpenRouter). Verify both personas produce different opening statements from system prompt alone.

---

### Day 2: Opinions, Memory Test & Demo
*Goal: grounded opinions, proven memory, Week 3 handoff.*

**Person A (Backend)**
1. *(1.5 hrs)* Build `src/pipelines/opinion.py` — the deterministic sequential flow (persona + topic → forced retrieval call → wait for result → inject as grounding evidence → generate opinion + citations). Keep this as a dedicated pipeline rather than hoping the ReAct loop calls the tool on its own — it's the reliable way to guarantee the "grounded in retrieved evidence" requirement.
2. *(1 hr)* Write `tests/test_memory.py` — same `thread_id`, "my priority is latency" → later "what is my priority?" → assert the model reflects it back.
3. *(1 hr)* Write `src/handoff.py` — `get_response(agent_id, thread_id, user_message)` for Week 3.

**Person B (Prompts / Integration / Docs)**
1. *(1.5 hrs)* Opinion-generation prompts. Force exact `source_url` citation from retrieved context — tell the model to copy the URL verbatim rather than reconstruct it, to avoid hallucinated links.
2. *(1 hr)* Write `demo.py`: load personas → topic → Agent A retrieves + opines → Agent B retrieves (different evidence) + opines → show the divergence in sources and reasoning.
3. *(1 hr)* Write `README.md` per assignment §20 (architecture, persona, memory, tools, LLM selection) plus exact reproduction commands. Include the Limitations section — this is also where the context-overflow decision from Day 1 gets documented either way.

---

## 5. Repository Structure

Unchanged from the original — it was already good:

```text
.
├── .env.example
├── requirements.txt
├── personas/
│   ├── __init__.py
│   ├── base.py
│   └── personas.json
├── prompts/
│   ├── system.jinja
│   └── opinion.jinja
├── src/
│   ├── agent/
│   │   ├── state.py
│   │   └── graph.py
│   ├── tools/
│   │   └── retrieval.py
│   ├── llm/
│   │   └── client.py
│   └── pipelines/
│       └── opinion.py
├── tests/
│   ├── test_memory.py
│   └── test_tools.py
├── demo.py
└── README.md
```

---

## 6. Critical Implementation Notes

### Enforcing different retrieval per persona
> **📝 Note — rewritten from the original "Hack 1."** Same effect, no hardcoded branching.

Don't let the LLM freely decide the query, and don't branch on persona name in code. Read the instruction straight from persona config:
```python
retrieval_hint = f"When using the retrieval tool, search for: {persona.retrieval_focus}"
```
Works identically for 2 personas or 20 — adding a new persona is a JSON file, never a code change.

### Memory for Week 3
Memory is handled by the checkpointer (confirmed class name — see §1 note). Same `thread_id` across calls = full conversation history available in state. This is your memory test's whole mechanism.

### Source grounding
Instruct the opinion prompt strictly: attribute claims to specific sources, format citations as `[Source: URL]`, copy URLs verbatim from tool output (don't let the model retype them), and acknowledge counter-evidence before pivoting if retrieved evidence cuts against the persona's stance.

---

## 7. Risk Mitigation

- **Week 1 DB is slow** → `top_k=5`, timeout + try/except around the retriever so the agent degrades gracefully ("knowledge base unreachable") instead of crashing.
- **LLM hallucinated citations** → hardcode `\n\nURL: {url}` into tool output; instruct the model to copy exactly.
- **Context window overflow** → *(now explicitly assigned in Day 1, Person A — see note above; don't let this stay a fictional mitigation)*.

---

## 8. Handoff Deliverable for Week 3

Unchanged — single entry point:
```python
from src.agent.graph import get_agent

agent_a = get_agent(persona="persona_a")
response = agent_a.invoke({"messages": ["What is your view on MoE?"]})
```
Document it clearly so Week 3 can import and plug into a multi-agent group chat without reading your internals.

---

**Summary of changes from the original:** persona-branching hardcode replaced with a config field (§3, §6) — this one's required by the spec, not optional; checkpointer class name needs verification before use (§1); Week 1 copy scoped down to just retrieval (§1); a 15-minute schema-alignment step added before the split (§2); context-overflow mitigation given an explicit owner or an explicit "we're skipping this, here's why" (§4, §7). Everything else — topology, task breakdown, demo structure, handoff interface — carried over as-is because it was already right.