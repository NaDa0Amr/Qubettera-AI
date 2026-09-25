"""AgentState definition for the LangGraph agent.

Week 2 additions:
    memory_summary           — rolling LLM summary of older conversation turns
    summarized_message_count — message index up to which summary covers
    tool_rounds_used         — tool rounds consumed in the current turn
    max_tool_rounds          — per-turn tool-round budget
    kb_rounds_used           — knowledge-base rounds consumed in the current turn
    web_rounds_used          — web-tool rounds consumed in the current turn
    kb_insufficient          — the KB's best hit scored below MIN_TOP_SIMILARITY
    web_searches_used        — web searches consumed in the current turn
    max_web_searches         — per-turn web-search budget
    max_web_rounds           — per-turn budget of web rounds
    final_round              — whether this is the discussion's last round
    retrieved_docs           — structured retrieval results accumulated during run
    web_documents            — structured web search results accumulated during run
    retrieval_queries        — list of queries issued during this run
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # --- SYSTEM INPUT ---
    task: str               # The discussion topic or question

    # --- WORKING MEMORY (LangGraph managed) ---
    messages: Annotated[List[Any], add_messages]  # full chat history

    # --- ROLLING SUMMARY (overflow protection) ---
    memory_summary: str           # LLM-generated summary of older turns
    summarized_message_count: int # how many messages are already summarized

    # --- EXTERNAL CONTEXT ---
    neighbor_opinions: Dict[str, str]  # adjacent agent ID -> their last opinion

    # --- STATIC CONFIG ---
    persona: Dict[str, Any]  # loaded PersonaConfig dict

    # --- TOOL BUDGET ---
    tool_rounds_used: int      # tool rounds consumed in the *current* turn
    max_tool_rounds: int       # per-turn tool-round budget
    kb_rounds_used: int        # knowledge-base rounds consumed this turn
    web_rounds_used: int       # web-tool rounds consumed this turn
    kb_insufficient: bool      # KB's best hit scored below MIN_TOP_SIMILARITY
    web_searches_used: int     # web searches consumed in the *current* turn
    max_web_searches: int      # per-turn web-search budget
    max_web_rounds: int        # per-turn budget of web *rounds*
    final_round: bool          # the discussion's last round (framing only)

    # --- TOOL OUTPUTS ---
    retrieved_docs: List[Dict[str, Any]]   # accumulated RAG results
    web_documents: List[Dict[str, Any]]    # accumulated web search results
    retrieval_queries: List[str]           # all queries issued this run

    # --- FINAL OUTPUT ---
    final_opinion: str  # last assistant response text
