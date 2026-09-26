import inspect

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
    _query_variants,
    _retrieval_is_weak,
    _weighted_rrf_fuse,
)
from qubettera.rag.query_expansion import parse_expansion_response
from qubettera.rag.paper_filter import parse_review_response, review_potential_drop
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


def test_rrf_preserves_contextual_embedding_text():
    vector_results = [{
        "chunk_id": "a1",
        "text": "evidence",
        "embedding_text": "Document title: Paper\n\nevidence",
    }]
    result = _rrf_fuse(vector_results, [])[0]
    assert result["embedding_text"] == "Document title: Paper\n\nevidence"


def test_weighted_rrf_rewards_candidates_found_by_multiple_query_variants():
    original = [{"chunk_id": "a", "text": "A"}, {"chunk_id": "b", "text": "B"}]
    expansion = [{"chunk_id": "b", "text": "B"}]

    results = _weighted_rrf_fuse(
        [(original, 1.0, "original"), (expansion, 0.7, "expanded")]
    )

    assert results[0]["chunk_id"] == "b"
    assert results[0]["matched_queries"] == ["original", "expanded"]


def test_query_expansion_keeps_original_first_and_deduplicates_variants():
    variants = _query_variants(
        "mixture of experts routing",
        expand=True,
        expansion_count=3,
        query_expander=lambda query, count: [
            query.upper(),
            "sparse expert load balancing",
            "MoE token routing capacity",
        ],
    )

    assert variants == [
        "mixture of experts routing",
        "sparse expert load balancing",
        "MoE token routing capacity",
    ]


def test_query_expansion_parser_accepts_json_and_rejects_original_query():
    response = '["linear attention", "softmax approximation kernels", "attention tradeoffs"]'

    assert parse_expansion_response(response, "linear attention", 2) == [
        "softmax approximation kernels",
        "attention tradeoffs",
    ]


def test_query_expansion_failure_falls_back_to_original(caplog):
    def broken_expander(query, count):
        raise RuntimeError("provider unavailable")

    assert _query_variants(
        "flash attention memory efficiency",
        expand=True,
        expansion_count=2,
        query_expander=broken_expander,
    ) == ["flash attention memory efficiency"]


def test_adaptive_expansion_only_marks_low_similarity_results_as_weak():
    assert _retrieval_is_weak([{"similarity": 0.31}], min_similarity=0.55)
    assert not _retrieval_is_weak([{"similarity": 0.72}], min_similarity=0.55)
    assert _retrieval_is_weak([], min_similarity=0.55)


def test_paper_review_parser_requires_an_explicit_keep_or_drop_decision():
    assert parse_review_response(
        '```json\n{"decision":"keep","reason":"directly evaluates MoE routing"}\n```'
    )["decision"] == "keep"
    with pytest.raises(ValueError, match="keep/drop"):
        parse_review_response('{"decision":"maybe"}')


def test_paper_llm_review_is_reused_from_the_content_cache(monkeypatch):
    calls = []
    monkeypatch.setenv("PAPER_FILTER_LLM_ENABLED", "true")

    def fake_review(title, text):
        calls.append((title, text))
        return {"decision": "drop", "reason": "only a passing citation"}

    monkeypatch.setattr("qubettera.rag.paper_filter._review_with_llm", fake_review)
    cache = {}
    first = review_potential_drop("Paper", "Body", cache)
    second = review_potential_drop("Paper", "Body", cache)

    assert first["cached"] is False
    assert second["cached"] is True
    assert len(calls) == 1


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


def test_retrieval_has_no_reranking_option():
    from qubettera.rag.retrieve import retrieve

    assert "rerank" not in inspect.signature(retrieve).parameters


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
