"""Conservative complete-request bounds shared by all discussion model calls.

UTF-8 bytes upper-bound ordinary byte-tokenizer tokens. Counting serialized
messages and tool schemas (plus framing headroom) avoids tokenizer downloads.
Set MODEL_CONTEXT_TOKENS to the deployed model's actual context window.
"""
from __future__ import annotations

import json
import os
import re

from langchain_core.messages import HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool


def clip(text: str, limit: int) -> str:
    """Shorten text without splitting a URL or an exact source citation."""
    if len(text) <= limit:
        return text
    citations = list(dict.fromkeys(re.findall(r"\[Source: [^\]\n]+\]", text)))
    retained = []
    for citation in citations:
        if sum(len(item) + 1 for item in retained) + len(citation) + 4 <= limit:
            retained.append(citation)
    suffix = (" " + " ".join(retained)) if retained else ""
    end = max(0, limit - len(suffix) - 3)
    for match in re.finditer(r"\[Source: [^\]\n]+\]|https?://\S+", text):
        if match.start() < end < match.end():
            end = match.start()
            break
    prefix = text[:end]
    for citation in retained:
        prefix = prefix.replace(citation, "")
    return prefix + ("..." if limit >= 3 else "") + suffix


def clip_bytes(text: str, limit: int) -> str:
    """Apply the same atomic clipping under a UTF-8 byte allowance."""
    lo, hi = 0, min(len(text), limit)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(clip(text, mid).encode("utf-8")) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return clip(text, lo)



class InputBudget:
    def __init__(self, model=None):
        model_context = getattr(model, "num_ctx", None)
        configured = int(os.getenv("MODEL_CONTEXT_TOKENS", str(model_context or 32768)))
        self.context = min(configured, model_context) if model_context else configured
        self.answer = int(os.getenv("MODEL_ANSWER_TOKENS", "2048"))
        self.limit = self.context - self.answer - 512
        if self.answer <= 0 or self.limit < 1024:
            raise ValueError("Model context must leave at least 1024 input tokens after answer/framing reserves.")

    def size(self, messages, tools=()) -> int:
        payload = {"messages": [m.model_dump(exclude_none=True) for m in messages],
                   "tools": [convert_to_openai_tool(t) for t in tools]}
        return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))

    def fit(self, messages, tools=(), *, protected=()):
        """Retain system and latest exchange; discard oldest complete exchanges.

        Protected messages (current evidence/instructions) are never shortened.
        Tool call arguments and tool-result protocol are kept intact; oversized
        tool exchanges are replaced with a plain request to answer directly.
        """
        result = list(messages)
        while self.size([*result, *protected], tools) > self.limit:
            humans = [i for i, m in enumerate(result) if isinstance(m, HumanMessage)]
            if len(humans) > 1:
                del result[humans[0]:humans[1]]
                continue
            candidates = [i for i, m in enumerate(result)
                          if isinstance(m.content, str) and len(m.content) > 128
                          and not getattr(m, "tool_calls", None)]
            if candidates:
                index = max(candidates, key=lambda i: len(result[i].content))
                message = result[index]
                result[index] = message.model_copy(update={"content": clip(message.content, len(message.content) // 2)})
                continue
            if any(getattr(m, "tool_calls", None) for m in result):
                result = [m for m in result if m.type not in {"tool", "ai"}]
                result.append(HumanMessage(content="Answer from the current evidence. No further tools."))
                continue
            raise ValueError("Required instructions/evidence/tool schemas exceed the model input budget.")
        return [*result, *protected]

    def invoke(
        self,
        model,
        messages,
        tools=(),
        *,
        protected=(),
        config=None,
        stream: bool = False,
    ):
        fitted = self.fit(messages, tools, protected=protected)
        # Production LangChain models/runnables accept a generation cap. Tiny
        # scripted test models deliberately expose only invoke(messages).
        if hasattr(model, "bind"):
            invoke_kwargs = {"config": config} if config is not None else {}
            if stream:
                # BaseChatModel uses this flag to select its streaming transport
                # even when the caller ultimately wants one assembled AIMessage.
                invoke_kwargs["stream"] = True
            target = getattr(model, "bound", model)
            if hasattr(target, "num_predict"):
                # ChatOllama reads generation settings from model fields into
                # options. A top-level invoke kwarg is forwarded to Client.chat
                # verbatim and rejected. Copy rather than mutate the shared model.
                capped = target.model_copy(update={"num_predict": self.answer})
                if target is not model:
                    kwargs = dict(model.kwargs)
                    if kwargs.get("options") is not None:
                        kwargs["options"] = {**kwargs["options"], "num_predict": self.answer}
                    capped = model.model_copy(update={"bound": capped, "kwargs": kwargs})
                return capped.invoke(fitted, **invoke_kwargs)
            return model.bind(max_tokens=self.answer).invoke(fitted, **invoke_kwargs)
        return model.invoke(fitted)
