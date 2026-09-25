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
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from qubettera.agents.agent.state import AgentState
from qubettera.agents.llm.factory import _rate_limit_wait_seconds, get_chat_model
from qubettera.agents.tools.retrieval_tool import knowledge_retrieval, retrieve_knowledge_base
from qubettera.agents.tools.search_tool import live_web_search
from qubettera.agents.tools.crawl_tool import deep_web_crawl
from qubettera.agents.utils.debug_trace import parse_tool_sources
from qubettera.agents.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_DEFAULT_TOOLS = [knowledge_retrieval, retrieve_knowledge_base, live_web_search, deep_web_crawl]

# Tool names grouped by evidence source. The KB-first ladder needs to know which
# budget a call draws on: knowledge-base retrieval is capped by MAX_TOOL_ROUNDS,
# web tools by MAX_WEB_SEARCHES_PER_RUN / MAX_WEB_ROUNDS.
_KB_TOOL_NAMES = frozenset(
    {knowledge_retrieval.name, retrieve_knowledge_base.name, "knowledge_retrieval", "retrieve_knowledge_base"}
)
_WEB_TOOL_NAMES = frozenset({live_web_search.name, "live_web_search", deep_web_crawl.name, "deep_web_crawl"})
# Only live_web_search counts against the search cap; deep_web_crawl extracts a
# URL that a search already surfaced and has no budget of its own.
_WEB_SEARCH_TOOL_NAMES = frozenset({live_web_search.name, "live_web_search"})



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


def max_tool_rounds_per_turn() -> int:
    """Return the per-turn tool-round budget from ``MAX_TOOL_ROUNDS``.

    This is deliberately a per-*turn* budget. A discussion agent's message
    history is checkpointed across the whole discussion, so a tool-round count
    derived from ``messages`` would be a lifetime-of-agent count: after the
    first turn spends a round, every later turn would look exhausted and stop
    retrieving. Callers reset ``tool_rounds_used`` per turn and compare it to
    this budget instead.
    """
    raw = os.environ.get("MAX_TOOL_ROUNDS", "1")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"MAX_TOOL_ROUNDS must be an integer, got {raw!r}") from exc
    if value < 0:
        raise RuntimeError("MAX_TOOL_ROUNDS must be zero or greater.")
    return value


def max_web_searches_per_turn() -> int:
    """Return the per-turn web-search budget from ``MAX_WEB_SEARCHES_PER_RUN``.

    Like :func:`max_tool_rounds_per_turn`, this is deliberately a per-*turn*
    budget even though the variable predates that design. A discussion agent's
    message history is checkpointed across the whole discussion, so a web-search
    count derived from ``messages`` would be a lifetime-of-agent count: an agent
    that spent the budget in an early round would be silently locked out of web
    search for every later round. Callers reset ``web_searches_used`` per turn
    and compare it to this budget instead.
    """
    raw = os.environ.get("MAX_WEB_SEARCHES_PER_RUN", "5")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"MAX_WEB_SEARCHES_PER_RUN must be an integer, got {raw!r}") from exc
    if value < 0:
        raise RuntimeError("MAX_WEB_SEARCHES_PER_RUN must be zero or greater.")
    return value


def max_web_rounds_per_turn() -> int:
    """Return the per-turn budget of web *rounds* from ``MAX_WEB_ROUNDS``.

    ``MAX_TOOL_ROUNDS`` caps knowledge-base retrieval. Because one counter used
    to gate every tool, spending the KB round also ended the turn and the
    ``live_web_search`` fallback could never run: the model was told its
    evidence gathering was finished. This budget is deliberately separate so the
    web ladder stays reachable after the KB round is spent. Like the other
    budgets it is per *turn*: the caller resets the counter each turn.
    """
    raw = os.environ.get("MAX_WEB_ROUNDS", "1")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"MAX_WEB_ROUNDS must be an integer, got {raw!r}") from exc
    if value < 0:
        raise RuntimeError("MAX_WEB_ROUNDS must be zero or greater.")
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


def _document_dedup_keys(document: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    """Return every identity key that can match a retrieved document.

    The chunk identifier uniquely identifies a database chunk, but it is not
    present on web results or on provider evidence that was round-tripped
    through the tool envelope. Returning a URL+text key as well lets a document
    that carries a chunk ID still match an equivalent document that does not.
    """
    keys: list[tuple[str, ...]] = []
    chunk_id = document.get("chunk_id")
    if chunk_id:
        keys.append(("chunk_id", str(chunk_id)))
    url = str(document.get("url") or document.get("source_url") or "")
    text = str(document.get("text") or "")
    keys.append(("url_text", url, text[:200]))
    return tuple(keys)


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
    model_with_tools = base_model.bind_tools(list(registry.values()))

    # ------------------------------------------------------------------ #
    # manage_memory node                                                   #
    # ------------------------------------------------------------------ #
    def manage_memory(state: AgentState) -> dict[str, Any]:
        """Summarise older messages when history grows beyond the window."""
        messages = state.get("messages", [])
        cutoff = trim_start(messages)
        summarized_count = state.get("summarized_message_count", 0)

        if cutoff <= summarized_count:
            return {}  # nothing new to summarise

        prior_summary = state.get("memory_summary", "")
        new_old_messages = messages[summarized_count:cutoff]

        summary_prompt = (
            "Update the rolling conversation summary. Preserve user decisions, "
            "constraints, factual claims, and cited sources. Be concise.\n\n"
            f"Existing summary:\n{prior_summary or '(none)'}\n\n"
            f"New messages to fold in:\n{_transcript(new_old_messages)}"
        )
        try:
            response = base_model.invoke(
                [
                    SystemMessage(content="You maintain faithful, compact conversation memory."),
                    HumanMessage(content=summary_prompt),
                ]
            )
            summary_text = _content_text(response.content).strip()
            if not summary_text:
                return {}
            return {
                "memory_summary": summary_text,
                "summarized_message_count": cutoff,
            }
        except Exception as exc:
            logger.warning("memory summary failed (%s); keeping full history.", exc)
            return {}

    # ------------------------------------------------------------------ #
    # call_model node                                                       #
    # ------------------------------------------------------------------ #
    def call_model(state: AgentState) -> dict[str, Any]:
        """Invoke the LLM with the current conversation context."""
        if "persona" not in state:
            raise ValueError("AgentState requires a persona before call_model.")

        messages = state.get("messages", [])
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

        # Tool-loop control and final-round framing are separate concerns.
        # ``tools_exhausted`` only decides whether another retrieval round is
        # allowed this turn; ``final_round`` only decides whether the prompt
        # frames this as the final synthesis. Conflating them made every round
        # after the first look like a final round.
        tool_rounds_used = int(state.get("tool_rounds_used", 0) or 0)
        per_turn_budget = int(state.get("max_tool_rounds", max_tool_rounds_per_turn()))
        # Clamped to ``tool_rounds_used`` exactly as in ``tool_node``: a KB/web
        # round is a subset of the turn's tool rounds, so any larger value is a
        # stale checkpoint and must not make a reset turn look already spent.
        kb_rounds_used = min(int(state.get("kb_rounds_used", tool_rounds_used) or 0), tool_rounds_used)
        kb_insufficient = bool(state.get("kb_insufficient", False)) and kb_rounds_used > 0

        # Ladder mode is opted into by supplying ``max_web_rounds`` (the
        # discussion adapter does). Callers that omit it — handoff.py, the
        # opinion pipeline — keep the original single-budget semantics.
        kb_exhausted = False
        if "max_web_rounds" in state:
            web_rounds_used = min(int(state.get("web_rounds_used", 0) or 0), tool_rounds_used)
            max_web_rounds = int(state.get("max_web_rounds", max_web_rounds_per_turn()) or 0)
            max_web_searches = int(state.get("max_web_searches", max_web_searches_per_turn()) or 0)
            web_searches_used = int(state.get("web_searches_used", 0) or 0)
            # Mirror ``tool_node``: KB-first ordering is only enforced when a
            # knowledge-base tool is actually bound.
            kb_first_required = bool(_KB_TOOL_NAMES & set(registry))
            kb_available = kb_rounds_used < per_turn_budget
            # The web opens once the KB has been consulted, or immediately when
            # the KB's best hit was too weak to ground the question. It also
            # opens when no KB tool is bound at all — there is then nothing to
            # consult first, so requiring a KB round would close the web forever.
            web_available = (
                web_rounds_used < max_web_rounds
                and web_searches_used < max_web_searches
                and (kb_insufficient or kb_rounds_used > 0 or not kb_first_required)
            )
            # "Exhausted" must mean no tool at all is reachable. Treating a spent
            # KB round as exhausted closed the web path: the prompt told the
            # model its evidence gathering was over, so the fallback never ran.
            tools_exhausted = not kb_available and not web_available
            kb_exhausted = not kb_available and web_available
        else:
            tools_exhausted = kb_rounds_used >= per_turn_budget
        # A standalone agent run has no later round, so it is final by default;
        # only the discussion adapter sets this to False for intermediate rounds.
        final_round = bool(state.get("final_round", True))

        system_prompt = load_prompt(
            "system.jinja",
            persona=persona,
            task=task,
            neighbor_opinions=neighbor_opinions,
            memory_summary=memory_summary,
            synthesis_mode=tools_exhausted,
            kb_exhausted=kb_exhausted,
            max_web_searches=state.get("max_web_searches", max_web_searches_per_turn()),
            final_round=final_round,
        )

        active_model = model_with_tools

        try:
            response = active_model.invoke(
                [SystemMessage(content=system_prompt), *prompt_messages]
            )
        except Exception as exc:
            wait = _rate_limit_wait_seconds(str(exc))
            if wait and wait > 0:
                logger.warning("Groq rate limit reached; sleeping %.1fs and retrying...", wait)
                time.sleep(wait)
                try:
                    response = active_model.invoke(
                        [SystemMessage(content=system_prompt), *prompt_messages]
                    )
                except Exception as retry_exc:
                    logger.warning("Retry with tools failed (%s); answering directly.", retry_exc)
                    no_tools_prompt = system_prompt + "\n\nCRITICAL: Answer directly in plain text. Do NOT call any tools."
                    response = base_model.invoke(
                        [SystemMessage(content=no_tools_prompt), *prompt_messages]
                    )
            else:
                logger.warning("Tool-bound invocation failed (%s); answering directly.", exc)
                no_tools_prompt = system_prompt + "\n\nCRITICAL: Answer directly in plain text. Do NOT call any tools."
                response = base_model.invoke(
                    [SystemMessage(content=no_tools_prompt), *prompt_messages]
                )

        if isinstance(response, AIMessage) and response.tool_calls and tools_exhausted:
            logger.info("Model proposed tool call with tool budget spent; overriding with direct response...")
            direct_msg = HumanMessage(
                content=(
                    "Synthesize your final persona recommendation now in markdown text. "
                    "Do NOT call any tools. Cite your sources."
                    if final_round
                    else "Respond to your peers' routed arguments now in markdown text. "
                    "Do NOT call any more tools. Cite your sources."
                )
            )
            response = base_model.invoke(
                [SystemMessage(content=system_prompt), *prompt_messages, direct_msg]
            )

        # If this turn has not used any tool round and the model answered
        # directly without tools, prompt it once to ground its answer.
        #
        # ``retrieved_docs`` is deliberately NOT part of this condition: the
        # discussion adapter pre-fills it with provider evidence on every turn,
        # so requiring it to be empty disabled the backstop for every round
        # after the first. ``tool_rounds_used == 0`` alone means "this turn has
        # not gathered tool evidence yet".
        if (
            # No point nudging when the graph was compiled without tools.
            registry
            and not tools_exhausted
            and tool_rounds_used == 0
            and isinstance(response, AIMessage)
            and not response.tool_calls
        ):
            task_str = str(task).lower()
            if any(k in task_str for k in ("evidence", "research", "architecture", "trade-off", "transformer")):
                logger.info("Model answered directly on initial turn; prompting for mandatory retrieval...")
                retry_msg = HumanMessage(
                    content=(
                        "MANDATORY STEP: Before providing your final recommendation, execute a "
                        "tool call (knowledge_retrieval or live_web_search) to gather grounded "
                        "evidence for your position. Do NOT provide your final answer yet."
                        if final_round
                        else "MANDATORY STEP: Before responding to your peers, execute a tool call "
                        "(knowledge_retrieval or live_web_search) to gather grounded evidence for "
                        "your position. Do NOT respond yet."
                    )
                )
                try:
                    retry_response = active_model.invoke(
                        [SystemMessage(content=system_prompt), *prompt_messages, retry_msg]
                    )
                    if isinstance(retry_response, AIMessage) and retry_response.tool_calls:
                        response = retry_response
                except Exception as exc:
                    logger.debug("Tool retry invocation skipped: %s", exc)

        final_opinion = ""
        if isinstance(response, AIMessage) and not response.tool_calls:
            final_opinion = _content_text(response.content).strip()
            if "<think>" in final_opinion:
                cleaned = re.sub(r"<think>.*?</think>", "", final_opinion, flags=re.DOTALL).strip()
                if cleaned:
                    final_opinion = cleaned
            logger.info("final opinion: %d chars", len(final_opinion))

        # A response with no tool calls and no usable text ends the turn with
        # nothing to publish. Because the thread is checkpointed across the
        # discussion, leaving it empty lets the caller's history scan resolve to
        # a *previous turn's* opinion, which is then published as this turn's
        # contribution. Give the model one explicit chance to answer in plain
        # text before handing back an empty opinion.
        if not final_opinion and isinstance(response, AIMessage) and not response.tool_calls:
            logger.warning("Model returned no usable text; retrying once for a direct answer.")
            nudge = HumanMessage(
                content=(
                    "Your previous response contained no answer text. Answer directly "
                    "in plain markdown now, using the evidence you already have. "
                    "Do NOT call any tools."
                )
            )
            try:
                retry_response = base_model.invoke(
                    [SystemMessage(content=system_prompt), *prompt_messages, nudge]
                )
                if isinstance(retry_response, AIMessage):
                    retry_text = _content_text(retry_response.content).strip()
                    if " thinking" in retry_text:
                        cleaned = re.sub(r" thinking.*?</think>", "", retry_text, flags=re.DOTALL).strip()
                        if cleaned:
                            retry_text = cleaned
                    if retry_text:
                        response = retry_response
                        final_opinion = retry_text
                        logger.info("Direct-answer retry produced %d chars.", len(final_opinion))
            except Exception as exc:
                logger.warning("Direct-answer retry failed: %s", exc)

        return {"messages": [response], "final_opinion": final_opinion}

    # ------------------------------------------------------------------ #
    # tool_node                                                             #
    # ------------------------------------------------------------------ #
    def tool_node(state: AgentState) -> dict[str, Any]:
        """Execute tool calls and accumulate structured results in state."""
        last = state.get("messages", [])[-1] if state.get("messages") else None
        if not isinstance(last, AIMessage) or not last.tool_calls:
            raise ValueError("tool_node requires a final AIMessage with tool_calls.")

        outputs: list[ToolMessage] = []
        retrieved_docs: list[dict] = list(state.get("retrieved_docs", []))
        web_documents: list[dict] = list(state.get("web_documents", []))
        queries: list[str] = list(state.get("retrieval_queries", []))

        # KB-first only means anything when a knowledge-base tool is actually
        # available. A graph compiled with a web-only (or custom) tool set has no
        # KB to consult, so requiring one would block the web forever.
        kb_tool_names = _KB_TOOL_NAMES & set(registry)
        kb_first_required = bool(kb_tool_names)

        # A "round" is one pass of this node, however many sister calls it holds:
        # parallel calls in a single AIMessage arrive together and share it. The
        # budgets therefore gate the pass, not each individual call — a live run
        # recorded three knowledge_retrieval calls inside one round. Per-pass
        # flags keep the counters from advancing more than once per pass.
        kb_round_counted = False
        web_round_counted = False

        # Per-turn budget: state is checkpointed per agent for the whole
        # discussion, so this must come from a counter the caller resets each
        # turn rather than from the accumulating ``messages`` history.
        max_web_searches = int(state.get("max_web_searches", max_web_searches_per_turn()) or 0)
        existing_web_searches = int(state.get("web_searches_used", 0) or 0)

        # KB-first ladder. ``kb_rounds_used`` falls back to ``tool_rounds_used``
        # for callers that predate the split, so their behaviour is unchanged.
        #
        # Both sub-counters are clamped to ``tool_rounds_used``: a KB/web round is
        # always a subset of the turn's tool rounds, so a value above it can only
        # be a stale checkpoint surviving a caller that reset ``tool_rounds_used``
        # but does not know about the newer fields. Without the clamp the reset
        # would look like a spent budget — the same sticky-state trap that
        # previously bit synthesis_mode and web_searches_used.
        raw_tool_rounds_used = int(state.get("tool_rounds_used", 0) or 0)
        kb_rounds_used = min(int(state.get("kb_rounds_used", raw_tool_rounds_used) or 0), raw_tool_rounds_used)
        web_rounds_used = min(int(state.get("web_rounds_used", 0) or 0), raw_tool_rounds_used)
        max_kb_rounds = int(state.get("max_tool_rounds", max_tool_rounds_per_turn()))
        max_web_rounds = int(state.get("max_web_rounds", max_web_rounds_per_turn()) or 0)
        # Availability is fixed for the whole pass, so every sister call in it
        # sees the same answer instead of racing the increments below.
        kb_round_available = kb_rounds_used < max_kb_rounds
        web_round_available = web_rounds_used < max_web_rounds
        # "The KB is insufficient" is only meaningful for a turn that actually
        # consulted it; otherwise the flag would leak across turns.
        kb_insufficient = bool(state.get("kb_insufficient", False)) and kb_rounds_used > 0

        # Order-preserving dedup so a tool loop cannot re-accumulate the same
        # chunk and inflate the evidence block with repeated sources.
        seen_keys = {key for doc in retrieved_docs for key in _document_dedup_keys(doc)}

        for call in last.tool_calls:
            name = call.get("name", "")
            call_id = call.get("id", "")
            args = call.get("args", {})

            if name not in registry:
                content = json.dumps({"error": "Unknown tool", "documents": []})
            elif name in _KB_TOOL_NAMES and not kb_round_available:
                logger.info("Knowledge-base round budget spent (%d); skipping retrieval.", max_kb_rounds)
                content = json.dumps({"error": "Knowledge-base round budget spent for this turn.", "documents": []})
            elif name in _WEB_TOOL_NAMES and kb_first_required and not kb_insufficient and kb_rounds_used == 0:
                # KB-first: the knowledge base has not been consulted this turn
                # and there is no evidence that it is insufficient, so the web
                # must not be used before it.
                logger.info("Web tool requested before any knowledge-base round; enforcing KB-first.")
                content = (
                    "Knowledge-base first: call `knowledge_retrieval` before searching the web. "
                    "Web search is available once the knowledge base has been queried."
                )
            elif name in _WEB_SEARCH_TOOL_NAMES and existing_web_searches >= max_web_searches:
                logger.info("Web search limit reached (%d searches); skipping additional search.", max_web_searches)
                content = (
                    f"Web search limit reached (maximum {max_web_searches} searches allowed per turn). "
                    "Please synthesize your position using the evidence already retrieved."
                )
            elif name in _WEB_TOOL_NAMES and not web_round_available:
                logger.info("Web round budget spent (%d); skipping web tool.", max_web_rounds)
                content = (
                    f"Web round budget spent for this turn (maximum {max_web_rounds} web rounds). "
                    "Synthesize your position using the evidence already retrieved."
                )
            else:
                if name in _KB_TOOL_NAMES and not kb_round_counted:
                    kb_rounds_used += 1
                    kb_round_counted = True
                elif name in _WEB_TOOL_NAMES and not web_round_counted:
                    # A web *round* is one tool-node pass, however many searches
                    # it contains, so parallel calls in one round share a round.
                    web_rounds_used += 1
                    web_round_counted = True
                if name in _WEB_SEARCH_TOOL_NAMES:
                    existing_web_searches += 1
                try:
                    content = str(registry[name].invoke(args))
                except Exception as exc:
                    content = json.dumps({
                        "error": f"{type(exc).__name__}: {exc}",
                        "documents": [],
                    })

            parsed = _parse_tool_documents(content, name)
            if name in _KB_TOOL_NAMES:
                query = args.get("query") if isinstance(args, dict) else None
                if isinstance(query, str) and query not in queries:
                    queries.append(query)
                # If tool regenerated query via LLM, record regenerated query as well
                try:
                    envelope = json.loads(content)
                    if isinstance(envelope, dict):
                        if envelope.get("query_regenerated"):
                            regen_q = envelope.get("regenerated_query")
                            if regen_q and regen_q not in queries:
                                queries.append(regen_q)
                        # Latch KB quality so the web ladder can open when the
                        # knowledge base could not ground this turn's question.
                        if envelope.get("insufficient"):
                            kb_insufficient = True
                except Exception:
                    pass
                for document in parsed:
                    keys = _document_dedup_keys(document)
                    if any(key in seen_keys for key in keys):
                        continue
                    seen_keys.update(keys)
                    retrieved_docs.append(document)
            else:
                web_documents.extend(parsed)

            outputs.append(ToolMessage(content=content, tool_call_id=call_id, name=name))

        return {
            "messages": outputs,
            "retrieved_docs": retrieved_docs,
            "retrieval_queries": queries,
            "tool_rounds_used": int(state.get("tool_rounds_used", 0) or 0) + 1,
            "kb_rounds_used": kb_rounds_used,
            "web_rounds_used": web_rounds_used,
            "kb_insufficient": kb_insufficient,
            "web_searches_used": existing_web_searches,
            "web_documents": web_documents,
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

