"""Shared, versioned settings for chunking, embedding, and retrieval."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _positive_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer, got {raw_value!r}") from error
    if value <= 0:
        raise RuntimeError(f"{name} must be > 0, got {value}")
    return value

PIPELINE_VERSION = os.environ.get(
    "PIPELINE_VERSION", "rag-pipeline-2026.09.01-context-v1"
)
PREPROCESSING_VERSION = os.environ.get(
    "PREPROCESSING_VERSION", "clean-v2-chunk-v3-context"
)

EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"
)
EMBEDDING_MODEL_REVISION = os.environ.get("EMBEDDING_MODEL_REVISION", "main")
EMBEDDING_DIM = _positive_int_env("EMBEDDING_DIM", 1024)
EMBEDDING_BATCH_SIZE = _positive_int_env("EMBEDDING_BATCH_SIZE", 8)

RERANKER_MODEL = os.environ.get(
    "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)
RERANKER_MODEL_REVISION = os.environ.get("RERANKER_MODEL_REVISION", "main")

# Upper bound for a single retrieval query. Qwen3-Embedding accepts 32,768
# tokens, so this is a sanity guard rather than a model limit, and it must stay
# above the composite queries built by the discussion provider.
MAX_QUERY_CHARS = _positive_int_env("MAX_QUERY_CHARS", 2000)


def get_embedding_device() -> str:
    """Select CUDA when available while retaining a usable CPU fallback."""
    requested = os.environ.get("EMBEDDING_DEVICE", "auto").strip().lower()
    if requested == "auto":
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "EMBEDDING_DEVICE=cuda was requested, but CUDA is not available."
            )
    if requested not in {"cpu", "cuda"}:
        raise RuntimeError("EMBEDDING_DEVICE must be 'auto', 'cpu', or 'cuda'.")
    return requested

IVFFLAT_MAX_LISTS = _positive_int_env("IVFFLAT_MAX_LISTS", 100)
IVFFLAT_PROBES = _positive_int_env("IVFFLAT_PROBES", 100)
