"""LLM-backed query expansion for the retrieval pipeline."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _response_text(content: Any) -> str:
    """Normalize the common string and content-block chat response shapes."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content or "")


def parse_expansion_response(
    content: Any,
    original_query: str,
    max_expansions: int,
) -> list[str]:
    """Parse, normalize, and deduplicate query variants from an LLM response."""
    text = _response_text(content).strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()

    candidates: list[Any]
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        candidates = [
            re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line)
            for line in text.splitlines()
            if line.strip()
        ]
    else:
        if isinstance(payload, dict):
            payload = payload.get("queries", [])
        candidates = payload if isinstance(payload, list) else []

    normalized_original = " ".join(original_query.split()).casefold()
    variants: list[str] = []
    seen = {normalized_original}
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        query = " ".join(candidate.strip().strip("\"'").split())
        identity = query.casefold()
        if not query or len(query) > 512 or identity in seen:
            continue
        seen.add(identity)
        variants.append(query)
        if len(variants) >= max_expansions:
            break
    return variants


def expand_query_with_llm(query: str, count: int = 3) -> list[str]:
    """Generate focused alternate searches while keeping the original authoritative."""
    from langchain_core.messages import HumanMessage

    prompt = (
        "Generate alternate search queries for a technical research knowledge base.\n"
        f"Original query: {query}\n"
        f"Return exactly {count} complementary variants as a JSON array of strings. "
        "Each variant must contain 4-12 words and should use useful aliases, acronyms, "
        "paper terminology, or a different technical angle. Preserve the original intent; "
        "do not add unsupported facts. Return JSON only."
    )
    provider = os.environ.get("QUERY_EXPANSION_PROVIDER", "").strip().lower()
    model_name = os.environ.get("QUERY_EXPANSION_MODEL", "").strip() or None
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        model = ChatOllama(
            model=model_name or "qwen3:4b",
            base_url=os.environ.get(
                "QUERY_EXPANSION_BASE_URL", "http://localhost:11434"
            ),
            temperature=0,
            num_ctx=2048,
        )
    else:
        from qubettera.agents.llm.factory import get_chat_model

        model = get_chat_model(
            provider=provider or None,
            model=model_name,
        )

    response = model.invoke([HumanMessage(content=prompt)])
    return parse_expansion_response(response.content, query, count)
