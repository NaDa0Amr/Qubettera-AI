"""Debug tracing and source extraction utilities for agent runs."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any


def parse_markdown_sources(content: str, tool_name: str = "") -> list[dict[str, Any]]:
    """Extract structured source documents from markdown text.

    Supports:
      1. Standard search citation blocks:
         [1] **Title**
          URL: https://...
          snippet
      2. Crawl4AI document blocks:
         ## Title
         **URL:** https://...
         content
    """
    sources: list[dict[str, Any]] = []

    # Pattern for: [1] **Title**\n URL: https://...\n snippet
    pattern = re.compile(
        r"\[\d+\]\s+\*\*(.*?)\*\*\s*\n\s*URL:\s*(\S+)\s*\n\s*(.*?)(?=\n\[\d+\]|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        title, url, snippet = m.groups()
        sources.append(
            {
                "tool": tool_name,
                "title": title.strip(),
                "url": url.strip(),
                "snippet": snippet.strip(),
                "text": snippet.strip(),
            }
        )

    if not sources and content.startswith("## "):
        m_crawl = re.match(r"##\s+(.*?)\s*\n\s*\*\*URL:\*\*\s*(\S+)\s*\n(.*)", content, re.DOTALL)
        if m_crawl:
            title, url, text = m_crawl.groups()
            sources.append(
                {
                    "tool": tool_name,
                    "title": title.strip(),
                    "url": url.strip(),
                    "snippet": text.strip()[:300],
                    "text": text.strip(),
                }
            )

    return sources


def parse_tool_sources(content: str, tool_name: str = "") -> list[dict[str, Any]]:
    """Parse tool output into structured documents, handling both JSON and Markdown formats."""
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "documents" in data and isinstance(data["documents"], list):
            docs: list[dict[str, Any]] = []
            for doc in data["documents"]:
                if isinstance(doc, dict):
                    entry = dict(doc)
                    if tool_name and "tool" not in entry:
                        entry["tool"] = tool_name
                    docs.append(entry)
            return docs
    except (json.JSONDecodeError, TypeError):
        pass

    return parse_markdown_sources(content, tool_name)


def print_debug_info(result: dict[str, Any]) -> None:
    """Print detailed execution trace of tool calls, errors, and retrieved evidence."""
    messages = result.get("messages", [])

    tool_calls: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            content = str(msg.content)
            name = getattr(msg, "name", "") or "tool"
            sources.extend(parse_tool_sources(content, name))

    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for call in msg.tool_calls:
                tool_calls.append(call)

    print(f"\n[DEBUG: {len(sources)} chunk(s)/source(s) retrieved, {len(tool_calls)} tool call(s) made]")

    call_idx = 1
    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            content = str(msg.content)
            status = "OK"
            error: str | None = None

            try:
                data = json.loads(content)
                if isinstance(data, dict) and "error" in data:
                    status = "FAILED"
                    error = str(data["error"])
            except Exception:
                if (
                    content.startswith("Error performing live search")
                    or content.startswith("Failed to extract")
                    or content.startswith("Error crawling")
                ):
                    status = "FAILED"
                    error = content[:200]
                elif content.startswith("No results found"):
                    status = "EMPTY (No results)"
                else:
                    status = "OK"

            msg_name = getattr(msg, "name", "tool")
            print(f"  Tool Call {call_idx}: {msg_name} -> {status}")
            if error:
                print(f"     Error details: {error}")
            call_idx += 1

    print("\n  --- ACTUAL RETRIEVED CHUNKS / EVIDENCE FOR DEBUGGING ---")
    if not sources:
        print("  (No sources were retrieved or returned for this request)")

    for i, source in enumerate(sources, 1):
        tool = source.get("tool", "unknown_tool")
        title = source.get("title") or "Untitled Source"
        url = source.get("url") or ""
        score = source.get("score")

        info = f"  [{i}] Tool: {tool} | Title: {title}"
        if score is not None:
            try:
                info += f" | Score: {float(score):.4f}"
            except (ValueError, TypeError):
                info += f" | Score: {score}"
        if url:
            info += f"\n      URL: {url}"
        print(info)

        content = source.get("text") or source.get("snippet") or ""
        if content:
            cleaned = content.strip().replace("\r\n", "\n")
            lines = cleaned.splitlines()
            preview_lines = lines[:8]
            preview = "\n      ".join(preview_lines)
            if len(lines) > 8 or len(cleaned) > 500:
                preview += "\n      [...chunk content truncated for terminal preview...]"
            print(f"      Actual Chunk/Snippet Content:\n      {preview}\n")


def serialize_message(msg: Any, compact_tool_content: bool = True) -> dict[str, Any]:
    """Convert any LangChain BaseMessage or dict to a clean JSON-serializable dictionary.

    When compact_tool_content is True, tool message payloads (which repeat full
    document texts already recorded in retrieved_docs/web_documents) are replaced
    with concise summary references.
    """
    if isinstance(msg, dict):
        return {k: v for k, v in msg.items() if not k.startswith("_")}

    msg_type = getattr(msg, "type", "") or msg.__class__.__name__.lower().replace("message", "")
    content = getattr(msg, "content", "")

    # For tool messages, avoid duplicating multi-KB document JSON into message history
    if msg_type == "tool" and compact_tool_content:
        raw_str = str(content).strip()
        tool_name = getattr(msg, "name", "tool") or "tool"
        summary_content = ""
        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, dict) and "documents" in parsed:
                doc_count = len(parsed["documents"])
                regen_note = ""
                if parsed.get("query_regenerated"):
                    regen_note = f" (query regenerated: '{parsed.get('original_query')}' -> '{parsed.get('regenerated_query')}')"
                summary_content = f"[{tool_name} returned {doc_count} grounded document(s) -> stored in retrieved_docs{regen_note}]"
            elif isinstance(parsed, dict) and "error" in parsed:
                summary_content = f"[{tool_name} error: {parsed['error']}]"
        except Exception:
            pass

        if not summary_content:
            if "Web search limit reached" in raw_str:
                summary_content = raw_str
            elif raw_str.startswith("Error performing live search") or raw_str.startswith("Failed to extract"):
                summary_content = f"[{tool_name} failed: {raw_str[:250]}]"
            elif len(raw_str) > 250:
                summary_content = f"[{tool_name} completed -> results recorded in web_documents]"
            else:
                summary_content = raw_str

        content = summary_content

    serialized: dict[str, Any] = {
        "role": msg_type,
        "content": content,
    }

    name = getattr(msg, "name", None)
    if name:
        serialized["name"] = name

    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        serialized["tool_calls"] = tool_calls

    tool_call_id = getattr(msg, "tool_call_id", None)
    if tool_call_id:
        serialized["tool_call_id"] = tool_call_id

    response_metadata = getattr(msg, "response_metadata", None)
    if response_metadata:
        serialized["response_metadata"] = response_metadata

    additional_kwargs = getattr(msg, "additional_kwargs", None)
    if additional_kwargs:
        serialized["additional_kwargs"] = additional_kwargs

    return serialized


def extract_tool_calls_trace(messages: list[Any]) -> list[dict[str, Any]]:
    """Extract tool calls and correlate them with tool results.

    Deduplicated: omits raw multi-kilobyte JSON dumps, providing structured
    status, document counts, argument details, and execution summaries.
    """
    tool_results_by_id: dict[str, Any] = {}
    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            call_id = getattr(msg, "tool_call_id", "")
            if call_id:
                tool_results_by_id[call_id] = msg
            name = getattr(msg, "name", "")
            if name and name not in tool_results_by_id:
                tool_results_by_id[name] = msg

    calls_trace: list[dict[str, Any]] = []
    call_index = 1
    for msg in messages:
        calls = getattr(msg, "tool_calls", None) or []
        for call in calls:
            c_name = call.get("name", "")
            c_args = call.get("args", {})
            c_id = call.get("id", "")

            tool_msg = tool_results_by_id.get(c_id) or tool_results_by_id.get(c_name)
            raw_output = str(tool_msg.content) if tool_msg else ""

            status = "OK"
            error = None
            parsed_docs: list[dict[str, Any]] = []
            query_regen = False
            regen_from = None
            regen_to = None

            if raw_output:
                try:
                    data = json.loads(raw_output)
                    if isinstance(data, dict):
                        if "error" in data:
                            status = "FAILED"
                            error = str(data["error"])
                        if "documents" in data and isinstance(data["documents"], list):
                            parsed_docs = data["documents"]
                        if data.get("query_regenerated"):
                            query_regen = True
                            regen_from = data.get("original_query")
                            regen_to = data.get("regenerated_query")
                except Exception:
                    if (
                        raw_output.startswith("Error performing live search")
                        or raw_output.startswith("Failed to extract")
                        or raw_output.startswith("Error crawling")
                    ):
                        status = "FAILED"
                        error = raw_output[:300]
                    elif raw_output.startswith("No results found"):
                        status = "EMPTY"
                    elif "Web search limit reached" in raw_output:
                        status = "LIMIT_REACHED"
                        error = raw_output

            if status == "OK":
                summary = f"Successfully returned {len(parsed_docs)} grounded document(s)"
                if query_regen:
                    summary += f" (query reformulated via LLM: '{regen_from}' -> '{regen_to}')"
            elif status == "EMPTY":
                summary = "No documents matched the query"
            elif status == "LIMIT_REACHED":
                summary = "Web search limit reached (capped at 5 per agent)"
            else:
                summary = f"Tool execution failed: {error or 'unknown error'}"

            entry: dict[str, Any] = {
                "call_index": call_index,
                "tool_name": c_name,
                "arguments": c_args,
                "tool_call_id": c_id,
                "status": status,
                "documents_returned": len(parsed_docs),
                "summary": summary,
            }
            if error and status != "LIMIT_REACHED":
                entry["error"] = error
            if query_regen:
                entry["query_regenerated"] = True
                entry["original_query"] = regen_from
                entry["regenerated_query"] = regen_to

            calls_trace.append(entry)
            call_index += 1

    return calls_trace


def extract_all_sources(messages: list[Any], metadata_only: bool = True) -> list[dict[str, Any]]:
    """Extract all retrieved evidence sources from tool messages as a deduplicated citations list.

    When metadata_only=True, full duplicate text bodies are omitted (since they are
    already canonically stored in retrieved_docs and web_documents), keeping the
    citation index clean and concise.
    """
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            content = str(msg.content)
            name = getattr(msg, "name", "") or "tool"
            parsed = parse_tool_sources(content, name)
            for item in parsed:
                url = item.get("url") or item.get("source_url") or ""
                title = item.get("title") or ""
                key = (name, url, title)
                if key not in seen:
                    seen.add(key)
                    if metadata_only:
                        entry: dict[str, Any] = {
                            "tool": name,
                            "title": title or "Untitled",
                            "url": url,
                        }
                        if item.get("score") is not None:
                            entry["score"] = item.get("score")
                        if item.get("distance") is not None:
                            entry["distance"] = item.get("distance")
                        if item.get("rank") is not None:
                            entry["rank"] = item.get("rank")
                        snippet = item.get("snippet") or ""
                        if snippet:
                            snip_str = str(snippet).strip()
                            entry["snippet"] = snip_str[:160] + "..." if len(snip_str) > 160 else snip_str
                        sources.append(entry)
                    else:
                        sources.append(item)
    return sources


def stream_graph_with_trace(
    graph_instance: Any,
    initial_state: dict[str, Any],
    config: dict[str, Any],
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute graph using stream_mode='updates' and stream real-time debug information.

    Yields a live terminal trace of memory window checks, LLM planning,
    tool invocations, chunk retrieval, and synthesis progress.
    Returns the accumulated final state dict with step_trace and execution_duration_seconds.
    """
    start_time = time.time()
    accumulated_state = dict(initial_state)
    accumulated_state["messages"] = list(initial_state.get("messages", []))
    accumulated_state["retrieved_docs"] = list(initial_state.get("retrieved_docs", []))
    accumulated_state["web_documents"] = list(initial_state.get("web_documents", []))
    accumulated_state["retrieval_queries"] = list(initial_state.get("retrieval_queries", []))
    step_trace: list[dict[str, Any]] = []

    persona_name = initial_state.get("persona", {}).get("name", "Agent")
    print(f"\n🚀 Invoking graph for [{persona_name}] (thread_id: {config.get('configurable', {}).get('thread_id', 'unknown')})...")

    step_num = 1
    for update in graph_instance.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in update.items():
            if not isinstance(node_output, dict):
                continue

            # Merge updates into accumulated_state
            if "messages" in node_output and node_output["messages"]:
                accumulated_state["messages"].extend(node_output["messages"])
            if "final_opinion" in node_output and node_output["final_opinion"]:
                accumulated_state["final_opinion"] = node_output["final_opinion"]
            if "retrieved_docs" in node_output and node_output["retrieved_docs"]:
                accumulated_state["retrieved_docs"] = list(node_output["retrieved_docs"])
            if "web_documents" in node_output and node_output["web_documents"]:
                accumulated_state["web_documents"] = list(node_output["web_documents"])
            if "retrieval_queries" in node_output and node_output["retrieval_queries"]:
                accumulated_state["retrieval_queries"] = list(node_output["retrieval_queries"])
            if "memory_summary" in node_output and node_output["memory_summary"]:
                accumulated_state["memory_summary"] = node_output["memory_summary"]
            if "summarized_message_count" in node_output:
                accumulated_state["summarized_message_count"] = node_output["summarized_message_count"]

            # Real-time console reporting and trace recording
            if node_name == "manage_memory":
                summary = node_output.get("memory_summary")
                count = node_output.get("summarized_message_count", 0)
                step_trace.append({
                    "step": step_num,
                    "node": "manage_memory",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "summary_updated": bool(summary),
                    "summarized_message_count": count,
                })
                if summary:
                    print(f"  [{step_num}] ⚡ [Memory Manager] Older turns condensed into rolling summary.")
                else:
                    print(f"  [{step_num}] ✓ [Memory Manager] Window checked (message count within limit).")
                step_num += 1

            elif node_name == "call_model":
                msgs = node_output.get("messages", [])
                last = msgs[-1] if msgs else None
                tool_calls = getattr(last, "tool_calls", None) or []
                resp_meta = getattr(last, "response_metadata", {}) or {}
                step_entry: dict[str, Any] = {
                    "step": step_num,
                    "node": "call_model",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "tool_request" if tool_calls else "final_opinion",
                    "tool_calls": [
                        {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")}
                        for tc in tool_calls
                    ],
                    "response_metadata": resp_meta,
                }
                if tool_calls:
                    print(f"  [{step_num}] 🧠 [LLM Decision] Agent requested {len(tool_calls)} tool execution(s):")
                    for tc in tool_calls:
                        name = tc.get("name")
                        args = tc.get("args", {})
                        arg_preview = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}" for k, v in args.items())
                        print(f"       ⚙️  Tool Call: {name}({arg_preview})")
                else:
                    opinion_text = node_output.get("final_opinion") or getattr(last, "content", "")
                    cleaned_len = len(str(opinion_text).strip())
                    step_entry["opinion_char_count"] = cleaned_len
                    print(f"  [{step_num}] ✍️  [LLM Synthesis] Final opinion generated ({cleaned_len} characters).")
                step_trace.append(step_entry)
                step_num += 1

            elif node_name == "tools":
                new_retrieved = node_output.get("retrieved_docs", [])
                new_web = node_output.get("web_documents", [])
                total_chunks = len(new_retrieved) + len(new_web)
                step_trace.append({
                    "step": step_num,
                    "node": "tools",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "retrieved_docs_count": len(new_retrieved),
                    "web_documents_count": len(new_web),
                    "total_sources_received": total_chunks,
                    "queries": list(node_output.get("retrieval_queries", [])),
                })
                print(f"  [{step_num}] 🔧 [Tool Node] Executed tools -> Received {total_chunks} grounded evidence source(s).")
                for m in node_output.get("messages", []):
                    content_str = str(getattr(m, "content", ""))
                    if "query_regenerated" in content_str:
                        try:
                            env = json.loads(content_str)
                            if env.get("query_regenerated"):
                                print(f"       🔄 [LLM Query Reformulation] Low relevance on '{env.get('original_query')}' -> Regenerated to: '{env.get('regenerated_query')}'")
                        except Exception:
                            pass
                for doc in new_retrieved[:3]:
                    title = doc.get("title") or "Source"
                    score = doc.get("score") or doc.get("distance")
                    url = doc.get("url") or ""
                    print(f"       📄 Title: {title} (score: {score})")
                    if url:
                        print(f"          URL: {url}")
                step_num += 1

    accumulated_state["step_trace"] = step_trace
    accumulated_state["execution_duration_seconds"] = round(time.time() - start_time, 2)
    return accumulated_state

