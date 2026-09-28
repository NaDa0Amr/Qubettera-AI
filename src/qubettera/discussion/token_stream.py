"""LangChain callback that converts generation chunks into discussion events."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


TokenSink = Callable[[dict[str, Any]], None]


def _token_text(token: str | list[str | dict[str, Any]]) -> str:
    """Return displayable text from LangChain's string or content-block token."""
    if isinstance(token, str):
        return token

    parts: list[str] = []
    for block in token:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


class DiscussionTokenCallback(BaseCallbackHandler):
    """Label streamed model tokens with their immutable discussion turn."""

    def __init__(
        self,
        sink: TokenSink,
        *,
        discussion_id: str,
        agent_id: str,
        round_number: int,
    ) -> None:
        self._sink = sink
        self._discussion_id = discussion_id
        self._agent_id = agent_id
        self._round_number = round_number

    def on_llm_new_token(
        self,
        token: str | list[str | dict[str, Any]],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        text = _token_text(token)
        if not text:
            return
        self._sink(
            {
                "event": "token_chunk",
                "discussion_id": self._discussion_id,
                "agent_id": self._agent_id,
                "round": self._round_number,
                "token": text,
                "run_id": str(run_id),
            }
        )
