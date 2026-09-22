import json
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from qubettera.agents.pipelines import opinion


@pytest.fixture
def output_dir():
    path = Path(__file__).resolve().parent / ".generated" / uuid4().hex
    path.mkdir(parents=True)
    return path


class FakeModel:
    def __init__(self, text):
        self.text = text
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return AIMessage(content=self.text)


class FakeRetrievalTool:
    def __init__(self, callback):
        self.callback = callback

    def invoke(self, args):
        return self.callback(args)


def retrieval_payload():
    return json.dumps(
        {
            "documents": [
                {
                    "text": "Sparse experts lower active computation, but routing can be unstable.",
                    "url": "https://example.test/paper",
                    "title": "Architecture Study",
                    "score": 0.5,
                }
            ]
        }
    )


def test_opinion_forces_retrieval_cites_and_persists(monkeypatch, output_dir):
    calls = []
    monkeypatch.setattr(
        opinion,
        "retrieve_knowledge_base",
        FakeRetrievalTool(lambda args: calls.append(args) or retrieval_payload()),
    )
    model = FakeModel(
        "Routing is a real counter-risk, but sparse compute is compelling "
        "[Source: https://example.test/paper]"
    )
    result = opinion.generate_opinion(
        "moe_efficiency", "MoE or dense?", model=model, output_dir=output_dir
    )

    assert calls and "efficiency benchmarks" in calls[0]["query"]
    assert result["sources"][0]["url"] == "https://example.test/paper"
    saved = list(output_dir.glob("*.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text(encoding="utf-8"))["opinion_text"] == result["opinion_text"]
    assert "Grounding Evidence" in model.messages[-1].content


def test_opinion_stops_when_retrieval_fails(monkeypatch, output_dir):
    monkeypatch.setattr(
        opinion,
        "retrieve_knowledge_base",
        FakeRetrievalTool(
            lambda args: json.dumps(
                {"error": "knowledge base unreachable: timeout", "documents": []}
            )
        ),
    )
    with pytest.raises(opinion.OpinionGenerationError, match="unreachable"):
        opinion.generate_opinion(
            "dense_reliability", "MoE or dense?", model=FakeModel("unused"), output_dir=output_dir
        )


def test_personas_shape_different_queries_for_same_topic():
    from qubettera.agents.personas.loader import load_persona

    topic = "MoE or dense?"
    moe_query = opinion.build_retrieval_query(load_persona("moe_efficiency"), topic)
    dense_query = opinion.build_retrieval_query(load_persona("dense_reliability"), topic)
    assert moe_query != dense_query
    assert "FLOP" in moe_query
    assert "routing" in dense_query


def test_opinion_prompt_changes_stance_and_emphasis_by_persona():
    from qubettera.agents.personas.loader import load_persona

    documents = json.loads(retrieval_payload())["documents"]
    moe = load_persona("moe_efficiency")
    dense = load_persona("dense_reliability")
    moe_prompt = opinion.render_opinion_prompt(moe, "MoE or dense?", documents)
    dense_prompt = opinion.render_opinion_prompt(dense, "MoE or dense?", documents)
    assert moe_prompt != dense_prompt
    assert moe["stance"] in moe_prompt
    assert dense["stance"] in dense_prompt
    assert "quality per active parameter" in moe_prompt
    assert "training stability and reproducibility" in dense_prompt
