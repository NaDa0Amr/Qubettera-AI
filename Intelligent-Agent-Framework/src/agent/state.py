"""AgentState definition for the LangGraph agent.

Week 2 additions:
    memory_summary           — rolling LLM summary of older conversation turns
    summarized_message_count — message index up to which summary covers
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

    # --- TOOL OUTPUTS ---
    retrieved_docs: List[Dict[str, Any]]   # accumulated RAG results
    web_documents: List[Dict[str, Any]]    # accumulated web search results
    retrieval_queries: List[str]           # all queries issued this run

    # --- FINAL OUTPUT ---
    final_opinion: str  # last assistant response text
