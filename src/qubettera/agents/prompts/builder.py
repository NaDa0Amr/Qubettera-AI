"""Prompt assembly.

This is the one place that turns (persona + memory + evidence + tool
results) into actual text sent to the LLM. Keeping this separate from
personas.py and agent.py means the prompt *structure* can change without
touching persona data or the agent's control flow -- and means the same
persona data is available to render into a different prompt style later if
needed.

Two message-building entry points are exposed:
  build_system_prompt   persona identity + standing behavioral instructions
  build_opinion_prompt  the per-turn user message: topic + memory + evidence
"""

from __future__ import annotations

from qubettera.agents.memory.agent_memory import MemoryEntry
from qubettera.agents.personas.loader import PersonaConfig

MAX_MEMORY_ENTRIES_IN_PROMPT = 3
MAX_MEMORY_CHARS_PER_ENTRY = 250
MAX_EVIDENCE_CHUNKS_IN_PROMPT = 5
MAX_EVIDENCE_CHARS_PER_CHUNK = 500


def build_system_prompt(persona: PersonaConfig, *, tools_available: bool = True) -> str:
    """Render persona configuration into the system message.

    This is the mechanism by which persona information reaches the model:
    every field on PersonaConfig is rendered into an instruction here, so a
    new persona JSON file automatically produces a new system prompt with no
    code changes required.

    ``tools_available`` must match whether the caller is actually passing a
    ``tools=`` list to LLMClient.chat() for this request. Telling the model
    it can call search_knowledge_base when no tools were sent causes some
    providers (Groq included) to hard-reject the response with a 400 error
    ("Tool choice is none, but model called a tool") the moment the model
    tries to act on that instruction. Agent.interact() calls this with
    tools_available=False since it never passes tools; Agent.generate_opinion()
    uses the default (True) since it does.
    """
    expertise = ", ".join(persona.expertise) or "general knowledge"
    priorities = "; ".join(persona.priorities) or "no stated priorities"

    ground_rules = [
        "- Stay in character. Your opinions should visibly reflect your stance "
        "and priorities above, not a generic neutral summary.",
    ]
    if tools_available:
        ground_rules += [
            "- When you are given retrieved evidence, base your opinion on it "
            "and say which source(s) support your claim. Do not invent sources.",
            "- If the evidence is thin or contradicts your default stance, say "
            "so explicitly rather than ignoring it -- your skepticism level is "
            f"'{persona.skepticism_level}', which should show in how readily "
            "you accept a single source as sufficient.",
            "- Research strategy:\n"
            "  * Primary tool: Always search the internal knowledge base first using search_knowledge_base for foundational papers and architectures.\n"
            "  * Secondary fallback tool: If search_knowledge_base returns no relevant chunks, empty results, thin evidence, or encounters an error, then use search_web to find the missing information on the web (e.g. recent 2024-2026 benchmarks, live pricing, or external facts).\n"
            "  * Base your opinion on the retrieved chunks and cite them by title. Do not invent sources.",
        ]
    else:
        ground_rules += [
            "- No tools are available for this request. Answer directly from "
            "your persona's knowledge and the conversation history provided "
            "below. Do not attempt to call any tool.",
        ]

    return (
        f"You are {persona.name}.\n\n"
        f"Background: {persona.background}\n\n"
        f"Your default stance: {persona.stance}\n\n"
        f"Your areas of expertise: {expertise}.\n"
        f"What you prioritize when evaluating a claim or trade-off, in order: "
        f"{priorities}.\n\n"
        f"Communication style: {persona.communication_style}\n\n"
        "Ground rules:\n" + "\n".join(ground_rules)
    )


def build_memory_block(entries: list[MemoryEntry]) -> str:
    """Render past interactions into a block the model can use as context."""
    if not entries:
        return "(no earlier interactions on record)"
    trimmed = entries[-MAX_MEMORY_ENTRIES_IN_PROMPT:]
    lines = []
    for entry in trimmed:
        content = entry.content.strip()
        if len(content) > MAX_MEMORY_CHARS_PER_ENTRY:
            content = content[:MAX_MEMORY_CHARS_PER_ENTRY] + "..."
        lines.append(f"- [{entry.kind}, topic: {entry.topic}] {content}")
    return "\n".join(lines)


def build_evidence_block(evidence: list[dict]) -> str:
    """Render retrieved knowledge-base chunks into a citable evidence block."""
    if not evidence:
        return "(no evidence retrieved)"
    lines = []
    for item in evidence[:MAX_EVIDENCE_CHUNKS_IN_PROMPT]:
        text = str(item.get("text", ""))[:MAX_EVIDENCE_CHARS_PER_CHUNK]
        title = item.get("title") or item.get("document_id") or "unknown source"
        source_url = item.get("source_url") or "no URL recorded"
        lines.append(
            f"[Source: {title} | {source_url} | chunk_id={item.get('chunk_id')}]\n{text}"
        )
    return "\n\n".join(lines)


def build_opinion_prompt(
    *,
    topic: str,
    memory_entries: list[MemoryEntry],
    evidence: list[dict] | None = None,
) -> str:
    """Build the user-turn message asking the agent for an initial opinion.

    ``evidence`` is optional: pass None to let the model call the
    search_knowledge_base tool itself (agent.py's tool-calling loop), or pass
    already-retrieved results to skip straight to opinion generation.
    """
    memory_block = build_memory_block(memory_entries)
    parts = [
        f"Topic: {topic}\n",
        "Relevant information from your memory of earlier interactions:",
        memory_block,
        "",
    ]
    if evidence is not None:
        parts += [
            "Retrieved evidence from the knowledge base:",
            build_evidence_block(evidence),
            "",
        ]
    parts.append(
        "Give your initial opinion on this topic. Explicitly reference at "
        "least one retrieved source by title. Provide a clear, structured recommendation "
        "(with a concise comparison table or bullet points if comparing options). "
        "Ensure your opinion is complete, properly formatted, and concludes with your source citations without cutting off."
    )
    return "\n".join(parts)