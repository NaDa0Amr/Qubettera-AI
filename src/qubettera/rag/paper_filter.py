"""Cached LLM review for papers the deterministic cleaner would drop."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

REVIEW_VERSION = "paper-relevance-v1"
DEFAULT_CACHE_PATH = Path("data/paper_relevance_cache.json")


def _enabled() -> bool:
    return os.environ.get("PAPER_FILTER_LLM_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _identity(title: str, text: str) -> str:
    payload = f"{REVIEW_VERSION}\n{title.strip()}\n{text.strip()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_review_cache(path: Path = DEFAULT_CACHE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_review_cache(
    cache: dict[str, dict[str, Any]], path: Path = DEFAULT_CACHE_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block if isinstance(block, str) else str(block.get("text", ""))
            for block in content
            if isinstance(block, (str, dict))
        )
    return str(content or "")


def parse_review_response(content: Any) -> dict[str, Any]:
    text = _response_text(content).strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict) or payload.get("decision") not in {"keep", "drop"}:
        raise ValueError("paper review must return a keep/drop JSON decision")
    reason = str(payload.get("reason", "")).strip()[:500]
    return {"decision": payload["decision"], "reason": reason}


def _review_with_llm(title: str, text: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    provider = os.environ.get("PAPER_FILTER_LLM_PROVIDER", "").strip() or None
    model_name = os.environ.get("PAPER_FILTER_LLM_MODEL", "").strip() or None
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        model = ChatOllama(
            model=model_name or "qwen3:4b",
            base_url=os.environ.get(
                "PAPER_FILTER_LLM_BASE_URL", "http://localhost:11434"
            ),
            temperature=0,
            reasoning=False,
            num_ctx=8192,
            num_predict=256,
            format={
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["keep", "drop"]},
                    "reason": {"type": "string"},
                },
                "required": ["decision", "reason"],
            },
        )
    else:
        from qubettera.agents.llm.factory import get_chat_model

        model = get_chat_model(provider=provider, model=model_name)
    prompt = (
        "Decide whether this source belongs in a technical knowledge base about "
        "Transformer architecture, attention variants, mixture-of-experts, state-space "
        "models, instruction tuning, PPO/GRPO, or retrieval-augmented generation. "
        "Keep a paper when it contains substantive technical evidence relevant to at "
        "least one topic. Drop papers that only cite these topics, merely mention them, "
        "or are unrelated. Return JSON only as "
        '{"decision":"keep|drop","reason":"short explanation"}.\n\n'
        f"Title: {title}\n\nSource excerpt:\n{text[:8_000]}"
    )
    response = model.invoke([HumanMessage(content=prompt)])
    return parse_review_response(getattr(response, "content", response))


def review_potential_drop(
    title: str,
    text: str,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Return a cached/new verdict, or None when LLM review is disabled/unavailable."""
    if not _enabled():
        return None
    key = _identity(title, text)
    cached = cache.get(key)
    if isinstance(cached, dict) and cached.get("version") == REVIEW_VERSION:
        return {**cached, "cached": True}
    try:
        verdict = _review_with_llm(title, text)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "cached": False}
    stored = {**verdict, "version": REVIEW_VERSION}
    cache[key] = stored
    return {**stored, "cached": False}
