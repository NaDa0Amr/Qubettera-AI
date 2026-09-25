"""
Utility functions for agent operations.
Reused across Week 2 (demo) and Week 3 (multi-agent orchestration).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.messages import AIMessage

from qubettera.agents.personas.loader import load_all_personas


def _clean_opinion_text(text: str) -> str:
    """Remove reasoning/think tags and strip whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


def load_personas(filepath: str | None = None) -> List[Dict[str, Any]]:
    """
    Load persona configurations.
    Defaults to loading all validated individual persona configs from personas/.
    Falls back to reading from filepath if an explicit JSON file is provided.
    """
    if filepath:
        path = Path(filepath)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data

    try:
        personas_map = load_all_personas()
        return list(personas_map.values())
    except Exception:
        legacy_path = Path("personas/personas.json")
        if legacy_path.exists():
            with open(legacy_path, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


def get_persona_by_id(personas: List[Dict[str, Any]], persona_id: str) -> Dict[str, Any]:
    """
    Find a persona by its ID.
    
    Args:
        personas: List of persona dictionaries.
        persona_id: The ID to search for.
        
    Returns:
        The matching persona dictionary.
        
    Raises:
        ValueError: If no persona with the given ID is found.
    """
    matches = [p for p in personas if (p.get("id") or p.get("persona_id")) == persona_id]
    if not matches:
        raise ValueError(f"Persona with ID '{persona_id}' not found.")
    return matches[0]


def extract_opinion(
    result: Dict[str, Any],
    *,
    since: int | None = None,
    allow_history: bool = True,
) -> str:
    """
    Safely extract the final opinion from a LangGraph result dictionary.
    
    Strategy:
        1. Try the dedicated 'final_opinion' field.
        2. If empty, scan the messages list from end to start to find
            the first assistant message with non-empty content.
    
    Args:
        result: The result dictionary returned by graph.invoke().
        since: Index of the first message belonging to the current turn. When
            given, the reverse scan cannot look before it. A discussion agent's
            thread is checkpointed for the whole discussion, so without this
            boundary an empty response would resolve to a *previous turn's*
            opinion and be republished as if it were this turn's.
        allow_history: When False, a turn with no usable output returns an empty
            string instead of falling back to older turns. Callers that need to
            detect a genuinely empty turn (and retry or fail) pass False.
        
    Returns:
        The extracted opinion text, or an empty string if none found.
    """
    # 1. Try the dedicated field
    opinion = result.get("final_opinion", "")
    if opinion and "<tool_call>" not in str(opinion) and not str(opinion).strip().startswith('{"documents":'):
        cleaned = _clean_opinion_text(str(opinion))
        if cleaned:
            return cleaned

    # 2. Scan messages in reverse for the last assistant message with actual opinion content
    messages = result.get("messages", [])
    if since is not None and not allow_history:
        window = list(messages[since:])
    elif allow_history:
        window = list(messages)
    else:
        # No boundary given and history is disallowed: there is nothing
        # this turn can be shown to have produced.
        return ""

    for msg in reversed(window):
        is_assistant = (
            isinstance(msg, AIMessage)
            or getattr(msg, "type", "") == "ai"
            or (isinstance(msg, dict) and msg.get("role") == "assistant")
        )
        if not is_assistant:
            continue
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            continue

        content = ""
        if hasattr(msg, "content") and msg.content:
            content = str(msg.content).strip()
        elif isinstance(msg, dict) and msg.get("content"):
            content = str(msg["content"]).strip()

        if content and not content.startswith("<tool_call>") and not content.startswith('{"documents":'):
            cleaned = _clean_opinion_text(content)
            if cleaned:
                return cleaned
    return ""