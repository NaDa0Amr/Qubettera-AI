import inspect
import time

import pytest

from qubettera.rag.clean import relevance_check
from qubettera.rag.evaluate import (
    _ndcg_at_k,
    _result_matches,
    audit_corpus_coverage,
    compute_metrics,
    run_evaluation,
)
from qubettera.rag.retrieve import (
    _console_safe,
    _encode_query,
    _limit_per_source,
    _rrf_fuse,
    _validate_index_identity,
    _validate_top_k,
)
from qubettera.rag.run_pipeline import timed
from qubettera.rag.settings import (
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_REVISION,
    PIPELINE_VERSION,
    PREPROCESSING_VERSION,
)


def test_cleaner_keeps_a_document_with_one_specific_topic_term():
    _, strong_hits = relevance_check("FlashAttention improves transformer memory efficiency.")
    assert strong_hits == 1


def test_cleaner_normalizes_hyphenated_topic_phrases():
    _, strong_hits = relevance_check("Mixture-of-Experts routing")
    assert strong_hits >= 1


def test_retrieval_limits_chunks_per_source():
    results = [
        {"chunk_id": "a1", "url": "https://example/a"},
        {"chunk_id": "a2", "url": "https://example/a"},
        {"chunk_id": "b1", "url": "https://example/b"},
    ]
    assert [item["chunk_id"] for item in _limit_per_source(results, 1)] == ["a1", "b1"]


def test_rrf_preserves_contextual_text_for_reranking():
    vector_results = [{
        "chunk_id": "a1",
        "text": "evidence",
        "embedding_text": "Document title: Paper\n\nevidence",
    }]
    result = _rrf_fuse(vector_results, [])[0]
    assert result["embedding_text"] == "Document title: Paper\n\nevidence"


def test_source_limit_normalizes_arxiv_versions_and_trailing_slashes():
    results = [
        {"chunk_id": "a1", "url": "https://arxiv.org/abs/1234.56789v2/"},
        {"chunk_id": "a2", "url": "https://www.arxiv.org/abs/1234.56789"},
    ]
    assert [item["chunk_id"] for item in _limit_per_source(results, 1)] == ["a1"]


def test_text_hints_do_not_create_relevance():
    expected = {
        "relevant_sources": ["https://arxiv.org/abs/1234.56789"],
        "relevant_chunks": [{"url": "https://arxiv.org/abs/1234.56789", "hint": "attention"}],
    }
    unrelated = {
        "url": "https://arxiv.org/abs/9999.99999",
        "title": "Attention",
        "text": "attention attention",
    }
    assert not _result_matches(unrelated, expected)


def test_ndcg_uses_fixed_qrels_for_ideal_ranking():
    expected = {
        "relevant_sources": [
            "https://arxiv.org/abs/1111.11111",
            "https://arxiv.org/abs/2222.22222",
        ]
    }
    results = [{"url": "https://arxiv.org/abs/1111.11111"}]
    assert 0 < _ndcg_at_k(results, expected, k=5) < 1


def test_precision_at_k_uses_k_and_duplicate_sources_count_once():
    expected = {"relevant_sources": ["https://arxiv.org/abs/1111.11111"]}
    results = [
        {"url": "https://arxiv.org/abs/1111.11111"},
        {"url": "https://arxiv.org/abs/1111.11111v2"},
    ]
    metrics = compute_metrics(results, expected, k=5)
    assert metrics["precision_at_k"] == 0.2
    assert metrics["relevant_in_top_k"] == 1


def test_corpus_coverage_separates_missing_qrels():
    judgments = [{
        "query_id": "q1",
        "relevant_sources": ["https://example/a", "https://example/b"],
    }]
    coverage = audit_corpus_coverage(judgments, {"https://example/a"})
    assert coverage["available_qrel_sources"] == 1
    assert coverage["fully_covered_queries"] == 0
    assert coverage["mean_source_recall_ceiling"] == 0.5


def test_evaluation_allows_a_diagnostic_run_by_default():
    parameter = inspect.signature(run_evaluation).parameters["allow_incomplete_corpus"]
    assert parameter.default is True


def test_retrieval_defaults_to_evaluated_hybrid_only_mode():
    from qubettera.rag.retrieve import retrieve

    assert inspect.signature(retrieve).parameters["rerank"].default is False


def test_llm_visible_retrieval_tools_default_rerank_to_false():
    """The reranker measurably degrades every quality metric, so it stays off.

    ``rerank`` is part of the JSON schema the model sees, so a drift in these
    defaults would let an agent silently enable it at runtime.
    """
    from qubettera.agents.tools.retrieval_tool import knowledge_retrieval, retrieve_knowledge_base

    for tool in (knowledge_retrieval, retrieve_knowledge_base):
        schema = tool.args_schema.model_json_schema()
        assert schema["properties"]["rerank"]["default"] is False, tool.name
        assert "rerank" not in schema.get("required", []), tool.name


def test_reranker_is_never_enabled_from_live_code_paths():
    """No shipped source may turn the reranker on.

    The offline evaluation shows it losing hit@k, MRR, nDCG, precision and
    source recall, with the paired-bootstrap CIs entirely below zero.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    offenders = []
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # `rerank=True` as a keyword argument.
            if isinstance(node, ast.keyword) and node.arg == "rerank":
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    offenders.append(f"{path}:{node.lineno}")
            # `{"rerank": True}` as a dict entry passed to a tool.
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "rerank"
                        and isinstance(value, ast.Constant)
                        and value.value is True
                    ):
                        offenders.append(f"{path}:{node.lineno}")

    assert offenders == [], f"reranker enabled in shipped code: {offenders}"


def test_query_embedding_uses_model_retrieval_prompt_when_available():
    class PromptAwareModel:
        prompts = {"query": "retrieval prompt"}

        def encode(self, query, **kwargs):
            return query, kwargs

    query, kwargs = _encode_query(PromptAwareModel(), "mixture of experts")
    assert query == "mixture of experts"
    assert kwargs["prompt_name"] == "query"
    assert kwargs["normalize_embeddings"] is True


def test_query_embedding_remains_compatible_with_models_without_prompts():
    class PlainModel:
        def encode(self, query, **kwargs):
            return query, kwargs

    _, kwargs = _encode_query(PlainModel(), "attention")
    assert "prompt_name" not in kwargs


def test_candidate_pool_cannot_be_smaller_than_top_k():
    with pytest.raises(ValueError, match="candidate_pool"):
        _validate_top_k(5, 4)


def test_retrieval_rejects_incompatible_index_identity():
    manifest = {
        "embedding_models": [EMBEDDING_MODEL],
        "embedding_model_revisions": [EMBEDDING_MODEL_REVISION],
        "preprocessing_versions": [PREPROCESSING_VERSION],
        "pipeline_versions": [PIPELINE_VERSION],
        "missing_identity_columns": [],
    }
    _validate_index_identity(manifest)
    with pytest.raises(RuntimeError, match="incompatible"):
        _validate_index_identity({**manifest, "preprocessing_versions": ["old"]})


def test_pipeline_timer_does_not_report_success_after_failure(capsys):
    with pytest.raises(ValueError):
        with timed("broken step"):
            raise ValueError("boom")
    output = capsys.readouterr().out
    assert "[FAILED] broken step" in output
    assert "[OK] broken step" not in output


def test_console_safe_replaces_unsupported_characters(monkeypatch):
    class LegacyStdout:
        encoding = "cp1252"

    monkeypatch.setattr("qubettera.rag.retrieve.sys.stdout", LegacyStdout())
    assert _console_safe("result ‣ section") == "result ? section"


def test_concurrent_model_loaders_share_a_single_instance():
    """Discussion turns retrieve in parallel, so the lazy singletons must not
    let racing threads each build their own copy of the weights."""
    import threading

    import qubettera.rag.retrieve as retrieve
    builder_calls: list[int] = []

    def slow_builder():
        builder_calls.append(1)
        time.sleep(0.2)
        return object()

    original_builder = retrieve._build_embed_model
    original_model = retrieve._embed_model
    try:
        retrieve._build_embed_model = slow_builder
        retrieve._embed_model = None
        barrier = threading.Barrier(8)
        loaded: list[object] = []

        def worker():
            barrier.wait()
            loaded.append(retrieve._get_embed_model())

        workers = [threading.Thread(target=worker) for _ in range(8)]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join()
    finally:
        retrieve._build_embed_model = original_builder
        retrieve._embed_model = original_model

    assert len(builder_calls) == 1
    assert len({id(model) for model in loaded}) == 1


def test_query_limit_matches_the_discussion_provider_budget():
    """A 512-character cap silently broke every live discussion turn because
    the provider composes much longer composite queries."""
    from qubettera.discussion.retrieval_provider import _MAX_QUERY_CHARS
    from qubettera.rag.retrieve import _validate_query
    from qubettera.rag.settings import MAX_QUERY_CHARS

    assert _MAX_QUERY_CHARS == MAX_QUERY_CHARS
    assert _validate_query("x" * MAX_QUERY_CHARS) == "x" * MAX_QUERY_CHARS
    with pytest.raises(ValueError, match="too long"):
        _validate_query("x" * (MAX_QUERY_CHARS + 1))


def test_opinion_query_truncation_respects_the_shared_limit():
    from qubettera.agents.pipelines.opinion import build_retrieval_query
    from qubettera.agents.personas.loader import load_persona
    from qubettera.rag.retrieve import _validate_query
    from qubettera.rag.settings import MAX_QUERY_CHARS

    persona = load_persona("moe_efficiency")
    assert len(build_retrieval_query(persona, "topic")) <= MAX_QUERY_CHARS
    assert _validate_query(build_retrieval_query(persona, "x" * (MAX_QUERY_CHARS * 2)))
