"""Integration checks for the analytics package in the main project."""

from pathlib import Path
from uuid import uuid4

from PIL import Image
import pytest

from qubettera.analytics.engine import get_analytics
from qubettera.analytics.loader import DiscussionLog, OpinionSnapshot, load_discussion
from qubettera.analytics.opinion_change import track_opinion_change
from qubettera.analytics.report import render_report
from qubettera.analytics.sentiment import SentimentResult, score_sentiment
from qubettera.analytics.stance_scorer import StanceResult, StanceScorer
from qubettera.analytics.visualize import create_visualizations, build_interaction_graph
from qubettera.cli import _parser, _run_discussion


class FakeSentimentScorer:
    model_name = "test-scorer"

    def score_batch(self, texts, *, message_ids, agent_ids, rounds):
        return [
            SentimentResult(
                message_id=message_ids[index], agent_id=agent_ids[index],
                round=rounds[index], sentiment=0.0,
                label="neutral", confidence=1.0, method=self.model_name,
                text_length=len(text),
            )
            for index, text in enumerate(texts)
        ]


def test_saved_discussion_can_be_analyzed():
    path = Path(__file__).with_name("example.jsonl")

    log = load_discussion(path)
    assert log.agent_ids == ("a", "b")
    assert len(log.snapshots) == 4
    task1 = {"discussion_id": "example", "proposition": log.proposition(), "rows": [
        {"agent_id": agent, "round": round_number, "stance": stance, "change": None}
        for round_number in (0, 1)
        for agent, stance in (("a", -0.5), ("b", 0.5))
    ]}
    result = get_analytics(path, task1_result=task1, sentiment_scorer=FakeSentimentScorer())
    assert result["discussion_id"] == "example"
    assert result["rounds"] == [0, 1]
    assert len(result["opinion_change"]) == 4
    assert len(result["sentiment"]["messages"]) == 4
    report = render_report(result)
    for heading in ("Opinion Dynamics", "Agreement / Disagreement", "Influence", "Sentiment"):
        assert heading in report
    output_dir = Path("outputs") / f"analytics-test-{uuid4()}"
    try:
        paths = create_visualizations(result, output_dir)
        assert len(paths) == 2
        for path in paths.values():
            with Image.open(path) as image:
                assert image.format == "PNG"
                assert image.size[0] > 500
        graph = build_interaction_graph(result)
        assert set(graph.nodes) == {"a", "b"}
        assert set(graph.edges) == {("a", "b"), ("b", "a")}
    finally:
        if output_dir.exists():
            for child in output_dir.iterdir():
                child.unlink()
            output_dir.rmdir()


def test_analytics_command_accepts_saved_log():
    args = _parser().parse_args(["analytics", "run", "outputs/discussions/example.jsonl"])
    assert args.discussion == Path("outputs/discussions/example.jsonl")


def test_fake_discussion_cannot_request_analysis():
    args = _parser().parse_args(["discuss", "run", "--mode", "fake", "--analyze"])
    assert _run_discussion(args) == 2


def test_live_discussion_routes_completed_log_to_analytics(monkeypatch):
    from qubettera import cli
    from qubettera.discussion import orchestrator, retrieval_provider, week2_adapter

    class Runtime:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    class Orchestrator:
        def __init__(self, **kwargs):
            pass

        def run(self, config):
            return type("Result", (), {
                "discussion_id": "test", "status": "completed", "messages": ()
            })()

    seen = []
    monkeypatch.setattr(week2_adapter, "Week2AgentRuntime", Runtime)
    monkeypatch.setattr(retrieval_provider, "TeamRetrievalProvider", lambda: object())
    monkeypatch.setattr(orchestrator, "DiscussionOrchestrator", Orchestrator)
    monkeypatch.setattr(cli, "_run_analytics", lambda args: seen.append(args.discussion) or 0)
    assert cli.main(["discuss", "run", "--mode", "live", "--analyze"]) == 0
    assert len(seen) == 1 and seen[0].suffix == ".jsonl"


def test_stance_uses_injected_shared_chat_interface():
    class FakeChatModel:
        model = "test-model"

        def invoke(self, messages):
            assert messages[0][0] == "system"
            assert "dense" in messages[1][1]
            return type("Response", (), {"content": '{"stance": -0.5, "reasoning": "Prefers dense."}'})()

    result = StanceScorer(chat_model=FakeChatModel()).score(
        "Use MoE", "I prefer dense layers", 0
    )
    assert result.stance == -0.5
    assert result.reasoning == "Prefers dense."


@pytest.mark.parametrize("content", [
    '{"stance": 1, "reasoning": "Supports MoE."}',
    '```json\n{"stance": 1, "reasoning": "Supports MoE."}\n```',
    '`json\n{"stance": 1, "reasoning": "Supports MoE."}\n`',
])
def test_stance_accepts_single_json_object_with_optional_fence(content):
    class FakeChatModel:
        model = "test-model"

        def invoke(self, messages):
            return type("Response", (), {"content": content})()

    assert StanceScorer(chat_model=FakeChatModel()).score("Use MoE", "MoE works", 0).stance == 1


def test_stance_rejects_extra_text_around_json():
    class FakeChatModel:
        model = "test-model"

        def invoke(self, messages):
            return type("Response", (), {
                "content": 'Here is my answer: {"stance": 1, "reasoning": "Supports MoE."}'
            })()

    with pytest.raises(ValueError, match="invalid JSON"):
        StanceScorer(chat_model=FakeChatModel()).score("Use MoE", "MoE works", 0)


def test_opinion_change_tracks_each_agent_and_round():
    class FakeStanceScorer:
        def score(self, proposition, opinion_text, round_number):
            return StanceResult(0.2 + 0.2 * round_number, "test")

    result = track_opinion_change(
        Path(__file__).with_name("example.jsonl"), scorer=FakeStanceScorer()
    )
    assert len(result["rows"]) == 4
    for agent in ("a", "b"):
        rows = [row for row in result["rows"] if row["agent_id"] == agent]
        assert [row["stance"] for row in rows] == [0.2, 0.4]
        assert [row["change"] for row in rows] == [None, 0.2]


def test_sentiment_scores_message_content():
    log = DiscussionLog("example", "Objective", (), ("a",), (), (
        OpinionSnapshot("a", 0, "initial", "short opinion", message_id="m1",
                        content_text="A longer complete message"),
    ))
    rows = score_sentiment(log, scorer=FakeSentimentScorer())
    assert len(rows) == 1
    assert rows[0]["text_length"] == len("A longer complete message")
