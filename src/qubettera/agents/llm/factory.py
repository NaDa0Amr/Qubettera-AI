"""LLM factory supporting OpenRouter, Ollama, Groq, and W&B Inference.

Providers:
  - openrouter: ChatOpenRouter
  - ollama:     ChatOllama (local or ngrok)
  - groq:       ChatGroq (fast inference with retry logic)
  - wandb:      ChatOpenAI pointing to W&B serverless endpoint

Select provider via LLM_PROVIDER env var: openrouter | ollama | groq | wandb
"""
from __future__ import annotations

import os
import re
import time
import logging

from langchain_core.language_models import BaseChatModel
from ..utils import AgentCallbackHandler

logger = logging.getLogger(__name__)


def _number_env(name: str, default: str, cast):
    raw = os.environ.get(name, default)
    try:
        return cast(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} has an invalid value: {raw!r}") from exc


def _rate_limit_wait_seconds(error_message: str) -> float | None:
    """Parse Groq's 'Please try again in X.Xs' message and return seconds."""
    match = re.search(r"try again in (\d+(?:\.\d+)?)s", str(error_message), re.IGNORECASE)
    if match:
        return float(match.group(1)) + 0.5
    if any(k in str(error_message).lower() for k in ("rate_limit_exceeded", "payload too large", "413", "429")):
        return 60.0
    return None


def get_chat_model(
    provider: str | None = None,
    model: str | None = None,
    callback_handler: AgentCallbackHandler | None = None,
) -> BaseChatModel:
    """Factory for LangChain chat models that support tool calling.

    Providers:
        openrouter — ChatOpenRouter (default)
        ollama     — ChatOllama (local or ngrok)
        groq       — ChatGroq (fast free-tier)
    """
    provider = (
        provider
        or os.getenv("LLM_PROVIDER")
        or (
            "kaggle"
            if os.getenv("KAGGLE_LLM_URL") or os.getenv("KAGGLE_OLLAMA_URL")
            else "groq"
            if os.getenv("GROQ_API_KEY")
            else "openrouter"
        )
    ).strip().lower()
    model = model or os.getenv("LLM_MODEL")
    temperature = _number_env("LLM_TEMPERATURE", "0.7", float)

    local_handler = callback_handler or AgentCallbackHandler(
        verbose=os.getenv("LLM_VERBOSE", "false").lower() == "true"
    )
    callbacks = [local_handler]

    # Optionally add Langfuse
    if os.getenv("LANGFUSE_ENABLED", "false").lower() == "true":
        try:
            from langfuse.langchain import CallbackHandler
            callbacks.append(CallbackHandler())
        except Exception:
            logger.warning("Langfuse callback unavailable; check install and config.")

    if provider in {"kaggle", "kaggle-ollama"}:
        from langchain_ollama import ChatOllama

        base_url = os.getenv("KAGGLE_LLM_URL") or os.getenv("KAGGLE_OLLAMA_URL")
        if not base_url:
            raise RuntimeError(
                "KAGGLE_LLM_URL is required for LLM_PROVIDER=kaggle."
            )
        kaggle_model = model or os.getenv("KAGGLE_LLM_MODEL")
        if not kaggle_model:
            raise RuntimeError("KAGGLE_LLM_MODEL is required for LLM_PROVIDER=kaggle.")
        return ChatOllama(
            model=kaggle_model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=_number_env("KAGGLE_LLM_NUM_CTX", "8192", int),
            client_kwargs={
                "timeout": _number_env("LLM_TIMEOUT_SECONDS", "180", float)
            },
            callbacks=callbacks,
        )

    if provider == "openrouter":
        from langchain_openrouter import ChatOpenRouter  # type: ignore[import]

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for LLM_PROVIDER=openrouter.")
        return ChatOpenRouter(
            model=model or "google/gemma-4-26b-a4b-it:free",
            temperature=temperature,
            max_tokens=_number_env("OPENROUTER_MAX_TOKENS", "2048", int),
            timeout=_number_env("LLM_TIMEOUT_SECONDS", "60", int),
            max_retries=2,
            callbacks=callbacks,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model or os.getenv("OLLAMA_MODEL", "gemma3:4b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
            num_ctx=_number_env("OLLAMA_NUM_CTX", "4096", int),
            callbacks=callbacks,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq  # type: ignore[import]

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required for LLM_PROVIDER=groq.")
        groq_model = model or os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
        max_tokens = _number_env("GROQ_MAX_TOKENS", os.getenv("OPENROUTER_MAX_TOKENS", "2048"), int)
        return ChatGroq(
            model=groq_model,
            temperature=temperature,
            api_key=api_key,
            max_tokens=max_tokens,
            max_retries=5,
            callbacks=callbacks,
        )

    if provider in ("wandb", "wandb-inference"):
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("WANDB_API_KEY")
        if not api_key:
            raise RuntimeError("WANDB_API_KEY is required for LLM_PROVIDER=wandb.")
        base_url = os.getenv("WANDB_BASE_URL", "https://api.inference.wandb.ai/v1")
        project = os.getenv("WANDB_PROJECT")
        default_headers = {"project": project} if project else None
        return ChatOpenAI(
            model=model or os.getenv("WANDB_MODEL") or os.getenv("LLM_MODEL") or "Qwen/Qwen3.6-35B-A3B",
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=_number_env("WANDB_MAX_TOKENS", os.getenv("OPENROUTER_MAX_TOKENS", "2048"), int),
            reasoning_effort="none",
            default_headers=default_headers,
            callbacks=callbacks,
        )

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER {provider!r}; choose 'kaggle', 'openrouter', "
        "'ollama', 'groq', or 'wandb'."
    )
