"""LangGraph agent graph — build_graph() factory.

Week 2 merge additions:
  - build_graph() factory with injectable checkpointer (Nada pattern)
  - manage_memory node: rolling LLM summary when message count exceeds
    RECENT_EXCHANGES_TO_KEEP (default 5) to prevent context overflow
  - Custom tool_node: accumulates retrieved_docs and web_documents in state
  - Backward-compatible module-level `graph` using MemorySaver
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from qubettera.agents.agent.state import AgentState
from qubettera.agents.agent.budget import InputBudget, clip
from qubettera.agents.llm.factory import _rate_limit_wait_seconds, get_chat_model
from qubettera.agents.tools.retrieval_tool import knowledge_retrieval, retrieve_knowledge_base
from qubettera.agents.tools.search_tool import live_web_search
from qubettera.agents.tools.crawl_tool import deep_web_crawl
from qubettera.agents.utils.debug_trace import parse_tool_sources
from qubettera.agents.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_DEFAULT_TOOLS = [knowledge_retrieval, retrieve_knowledge_base, live_web_search, deep_web_crawl]



def recent_exchanges_to_keep() -> int:
    """Return the number of recent HumanMessage turns to keep verbatim."""
    raw = os.environ.get("RECENT_EXCHANGES_TO_KEEP", "5")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"RECENT_EXCHANGES_TO_KEEP must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise RuntimeError("RECENT_EXCHANGES_TO_KEEP must be greater than zero.")
    return value


def trim_start(messages: list[AnyMessage], exchanges: int | None = None) -> int:
    """Return the index at which to start passing messages to the model.

    Counts HumanMessage boundaries. If there are more than `keep` human
    turns, returns the index of the (len-keep)th human turn; otherwise 0.
    """
    keep = exchanges if exchanges is not None else recent_exchanges_to_keep()
    human_positions = [
        i for i, m in enumerate(messages) if isinstance(m, HumanMessage)
    ]
    if len(human_positions) <= keep:
        return 0
    return human_positions[-keep]


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)


def _transcript(messages: list[AnyMessage]) -> str:
    lines = []
    for m in messages:
        role = getattr(m, "type", m.__class__.__name__)
        lines.append(f"{role}: {_content_text(m.content)}")
    return "\n".join(lines)


def _parse_tool_documents(content: str, tool_name: str = "") -> list[dict[str, Any]]:
    """Parse structured documents from tool response (JSON envelope or Markdown citations)."""
    return parse_tool_sources(content, tool_name)


def build_graph(
    *,
    checkpointer: Any,
    model: BaseChatModel | None = None,
    tools: list | None = None,
    callbacks: list | None = None,
):
    """Compile the Week 2 agent graph with an injected checkpointer.

    Args:
        checkpointer: LangGraph checkpointer (MemorySaver or PostgresSaver).
        model:        Optional pre-built BaseChatModel. Defaults to factory.
        tools:        Optional tool list. Defaults to all 3 Week 2 tools.
        callbacks:    Optional extra LangChain callbacks.

    Returns:
        Compiled LangGraph CompiledGraph.
    """
    base_model = model or get_chat_model()
    active_tools = tools if tools is not None else _DEFAULT_TOOLS
    registry = {t.name: t for t in active_tools}
    if len(registry) != len(active_tools):
        raise ValueError("Tool names must be unique.")
    model_with_tools = base_model.bind_tools(list(registry.values())) if active_tools else base_model
    budget = InputBudget(base_model)

    # ------------------------------------------------------------------ #
    # manage_memory node                                                   #
    # ------------------------------------------------------------------ #
    def manage_memory(state: AgentState) -> dict[str, Any]:
        """Summarise older messages when history grows beyond the window."""
        messages = state.get("messages", [])
        cutoff = trim_start(messages)
        summarized_count = state.get("summarized_message_count", 0)

        if budget.size(messages) <= budget.limit // 2:
            return {}  # nothing new to summarise

        if cutoff <= summarized_count:
            humans = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
            cutoff = humans[-1] if len(humans) > 1 else 0
        if cutoff <= summarized_count:
            return {}
        prior_summary = clip(state.get("memory_summary", ""), 2000)
        new_old_messages = messages[summarized_count:cutoff]

        summary_prompt = (
            "Update the rolling conversation summary. Preserve user decisions, "
            "constraints, factual claims, and cited sources. Be concise.\n\n"
            f"Existing summary:\n{prior_summary or '(none)'}\n\n"
            f"New messages to fold in:\n{_transcript(new_old_messages)}"
        )
        try:
            response = budget.invoke(base_model,
                [
                    SystemMessage(content="You maintain faithful, compact conversation memory."),
                    HumanMessage(content=summary_prompt),
                ]
            )
            summary_text = _content_text(response.content).strip()
            if not summary_text:
                return {}
            return {
                "memory_summary": clip(summary_text, 2000),
                "summarized_message_count": cutoff,
            }
        except Exception as exc:
            logger.warning("memory summary failed (%s); using bounded recent history.", exc)
            return {}

    # ------------------------------------------------------------------ #
    # call_model node                                                       #
    # ------------------------------------------------------------------ #
    def call_model(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        """Invoke the LLM with the current conversation context."""
        if "persona" not in state:
            raise ValueError("AgentState requires a persona before call_model.")

        messages = state.get("messages", [])
        task = state.get("task", "")
        cutoff = trim_start(messages)
        summarized_count = state.get("summarized_message_count", 0)

        # Use windowed messages only if summary covers the old part
        if cutoff > 0 and summarized_count >= cutoff:
            prompt_messages = messages[cutoff:]
        else:
            prompt_messages = messages

        if not prompt_messages:
            prompt_messages = [HumanMessage(content=task or "Please provide your opinion.")]

        # Build system prompt via Jinja2 template
        persona = state["persona"]
        task = state.get("task", "")
        neighbor_opinions = state.get("neighbor_opinions", {})
        memory_summary = state.get("memory_summary", "")

        # Count tool turns to prevent runaway loops and token accumulation
        tool_count = state.get("tool_rounds", 0)
        max_tool_rounds = int(os.getenv("MAX_TOOL_ROUNDS", "1"))
        synthesis_mode = tool_count >= max_tool_rounds

        system_prompt = load_prompt(
            "system.jinja",
            persona=persona,
            task=task,
            neighbor_opinions=neighbor_opinions,
            memory_summary=memory_summary,
            synthesis_mode=synthesis_mode,
            discussion_mode=state.get("discussion_mode", False),
            tools_available=bool(active_tools),
        )

        active_model = base_model if synthesis_mode else model_with_tools
        shown = []
        protected = []
        if state.get("discussion_mode"):
            from qubettera.discussion.citations import RULES
            from qubettera.discussion.context import render_evidence_block
            from qubettera.discussion.models import EvidenceItem
            evidence_text = ""
            # Leave one slot for web fallback when external tools are available.
            internal_limit = 4 if active_tools else 5
            for document in [*state.get("retrieved_docs", [])[:internal_limit], *state.get("web_documents", [])]:
                if len(shown) >= 5:
                    break
                item = {**document, "text": clip(str(document.get("text", "")), 1200),
                        "title": clip(str(document.get("title", "")), 200)}
                block = render_evidence_block((EvidenceItem(text=item["text"], title=item["title"],
                    url=str(item.get("url") or item.get("source_url") or "")),))
                if len((evidence_text + block).encode("utf-8")) > budget.limit // 3:
                    continue
                evidence_text += block + "\n"
                shown.append(item)
            protected = [SystemMessage(content=RULES + "\nCurrent evidence only:\n" +
                (evidence_text or "No supporting evidence is available."))]

        def invoke(target, prompt):
            schemas = active_tools if target is model_with_tools and not synthesis_mode else ()
            stream_tokens = bool(config.get("configurable", {}).get("stream_tokens"))
            return budget.invoke(
                target,
                prompt,
                schemas,
                protected=protected,
                config=config,
                stream=stream_tokens,
            )

        try:
            response = invoke(active_model,
                [SystemMessage(content=system_prompt), *prompt_messages]
            )
        except Exception as exc:
            from httpx import ConnectError, TimeoutException

            if isinstance(exc, (ConnectError, TimeoutException)) or "ERR_NGROK_3200" in str(exc):
                raise RuntimeError(
                    "Generation model connection failed or timed out. Check the model endpoint "
                    "and LLM_TIMEOUT_SECONDS; live discussions use one worker by default."
                ) from exc
            wait = _rate_limit_wait_seconds(str(exc))
            if wait and wait > 0:
                logger.warning("Groq rate limit reached; sleeping %.1fs and retrying...", wait)
                time.sleep(wait)
                try:
                    response = invoke(active_model,
                        [SystemMessage(content=system_prompt), *prompt_messages]
                    )
                except Exception as retry_exc:
                    logger.warning("Retry with tools failed (%s); answering directly.", retry_exc)
                    no_tools_prompt = system_prompt + "\n\nCRITICAL: Answer directly in plain text. Do NOT call any tools."
                    response = invoke(base_model,
                        [SystemMessage(content=no_tools_prompt), *prompt_messages]
                    )
            else:
                logger.warning("Tool-bound invocation failed (%s); answering directly.", exc)
                no_tools_prompt = system_prompt + "\n\nCRITICAL: Answer directly in plain text. Do NOT call any tools."
                response = invoke(base_model,
                    [SystemMessage(content=no_tools_prompt), *prompt_messages]
                )

        if isinstance(response, AIMessage) and response.tool_calls and synthesis_mode:
            logger.info("Model proposed tool call in synthesis mode; overriding with direct response...")
            direct_msg = HumanMessage(
                content="Synthesize your final persona recommendation now in markdown text. Do NOT call any tools. Cite your sources."
            )
            response = invoke(base_model,
                [SystemMessage(content=system_prompt), *prompt_messages, direct_msg]
            )

        # If on the initial research turn (tool_count == 0) the model answered directly without tools,
        # prompt it once to execute a retrieval tool to ground its answer.
        if (
            not state.get("discussion_mode")
            and bool(active_tools)
            and not synthesis_mode
            and tool_count == 0
            and not state.get("retrieved_docs")
            and isinstance(response, AIMessage)
            and not response.tool_calls
        ):
            task_str = str(task).lower()
            if any(k in task_str for k in ("evidence", "research", "architecture", "trade-off", "transformer")):
                logger.info("Model answered directly on initial turn; prompting for mandatory retrieval...")
                retry_msg = HumanMessage(
                    content="MANDATORY STEP: Before providing your final recommendation, execute a tool call (knowledge_retrieval or live_web_search) to gather grounded evidence for your position. Do NOT provide your final answer yet."
                )
                try:
                    retry_response = invoke(active_model,
                        [SystemMessage(content=system_prompt), *prompt_messages, retry_msg]
                    )
                    if isinstance(retry_response, AIMessage) and retry_response.tool_calls:
                        response = retry_response
                except Exception as exc:
                    logger.debug("Tool retry invocation skipped: %s", exc)

        if synthesis_mode and isinstance(response, AIMessage) and response.tool_calls:
            response = AIMessage(content="No supporting evidence is available. Unable to complete a recommendation within the tool limit.")
        final_opinion = ""
        if isinstance(response, AIMessage) and not response.tool_calls:
            final_opinion = _content_text(response.content).strip()
            if "<think>" in final_opinion:
                cleaned = re.sub(r"<think>.*?</think>", "", final_opinion, flags=re.DOTALL).strip()
                if cleaned:
                    final_opinion = cleaned
            logger.info("final opinion: %d chars", len(final_opinion))

        return {"messages": [response], "final_opinion": final_opinion, "shown_documents": shown}

    # ------------------------------------------------------------------ #
    # tool_node                                                             #
    # ------------------------------------------------------------------ #
    MAX_WEB_SEARCHES_PER_RUN = 5

    def tool_node(state: AgentState) -> dict[str, Any]:
        """Execute tool calls and accumulate structured results in state."""
        last = state.get("messages", [])[-1] if state.get("messages") else None
        if not isinstance(last, AIMessage) or not last.tool_calls:
            raise ValueError("tool_node requires a final AIMessage with tool_calls.")

        outputs: list[ToolMessage] = []
        retrieved_docs: list[dict] = list(state.get("retrieved_docs", []))
        web_documents: list[dict] = list(state.get("web_documents", []))
        queries: list[str] = list(state.get("retrieval_queries", []))

        # Counters are reset by the discussion adapter at each turn entry.
        existing_web_searches = state.get("web_searches", 0)

        for call in last.tool_calls:
            name = call.get("name", "")
            call_id = call.get("id", "")
            args = call.get("args", {})

            if state.get("discussion_mode") and name in {"knowledge_retrieval", "retrieve_knowledge_base"}:
                content = json.dumps({"error": "Internal retrieval belongs to the orchestrator", "documents": []})
            elif name not in registry:
                content = json.dumps({"error": "Unknown tool", "documents": []})
            elif name in {live_web_search.name, "live_web_search"} and existing_web_searches >= MAX_WEB_SEARCHES_PER_RUN:
                logger.info("Web search limit reached (%d searches); skipping additional search.", MAX_WEB_SEARCHES_PER_RUN)
                content = (
                    f"Web search limit reached (maximum {MAX_WEB_SEARCHES_PER_RUN} searches allowed per agent run). "
                    "Please synthesize your position using the evidence already retrieved."
                )
            else:
                if name in {live_web_search.name, "live_web_search"}:
                    existing_web_searches += 1
                try:
                    content = str(registry[name].invoke(args))
                except Exception as exc:
                    content = json.dumps({
                        "error": f"{type(exc).__name__}: {exc}",
                        "documents": [],
                    })

            parsed = _parse_tool_documents(content, name)
            if state.get("discussion_mode"):
                remaining = max(0, 5 - min(len(retrieved_docs), 4) - len(web_documents))
                parsed = [{**d, "text": clip(str(d.get("text", "")), 1200),
                           "title": clip(str(d.get("title", "")), 200)} for d in parsed[:remaining]]
                # Only the separately budgeted current-evidence block exposes
                # documents to the model. Raw tool output cannot bypass it.
                content = ("Candidate evidence received; admitted sources are in the current-evidence block."
                           if parsed else "Tool failed or returned no additional usable evidence.")
            if name in {knowledge_retrieval.name, retrieve_knowledge_base.name, "knowledge_retrieval", "retrieve_knowledge_base"}:
                query = args.get("query") if isinstance(args, dict) else None
                if isinstance(query, str) and query not in queries:
                    queries.append(query)
                # If tool regenerated query via LLM, record regenerated query as well
                try:
                    envelope = json.loads(content)
                    if isinstance(envelope, dict) and envelope.get("query_regenerated"):
                        regen_q = envelope.get("regenerated_query")
                        if regen_q and regen_q not in queries:
                            queries.append(regen_q)
                except Exception:
                    pass
                retrieved_docs.extend(parsed)
            else:
                web_documents.extend(parsed)

            outputs.append(ToolMessage(content=content, tool_call_id=call_id, name=name))

        return {
            "messages": outputs,
            "retrieved_docs": retrieved_docs,
            "retrieval_queries": queries,
            "web_documents": web_documents,
            "tool_rounds": state.get("tool_rounds", 0) + 1,
            "web_searches": existing_web_searches,
        }

    # ------------------------------------------------------------------ #
    # Routing                                                               #
    # ------------------------------------------------------------------ #
    def route_after_model(state: AgentState) -> Literal["tools", "__end__"]:
        last = (state.get("messages") or [None])[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "__end__"

    # ------------------------------------------------------------------ #
    # Compile                                                               #
    # ------------------------------------------------------------------ #
    builder = StateGraph(AgentState)
    builder.add_node("manage_memory", manage_memory)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "manage_memory")
    builder.add_edge("manage_memory", "call_model")
    builder.add_conditional_edges("call_model", route_after_model, ["tools", END])
    builder.add_edge("tools", "call_model")
    return builder.compile(checkpointer=checkpointer)

