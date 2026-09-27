"""Exercise the HTTP contract against the shared discussion/analytics code."""
import asyncio
import json
import threading

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core import config
from backend.app.services import analytics_runner


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WEEK3_OUTPUT_DIR", tmp_path / "discussions")
    monkeypatch.setattr(config, "ANALYTICS_OUT_DIR", tmp_path / "analytics")
    monkeypatch.setattr(config, "ANALYTICS_VISUALS_DIR", tmp_path / "analytics" / "visuals")
    with TestClient(app) as client:
        yield client


def test_shared_personas_fake_stream_and_history(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200
    personas = client.get("/personas").json()
    expected = json.loads(config.DEFAULT_PERSONAS_PATH.read_text(encoding="utf-8"))
    assert [p["id"] for p in personas] == [p["id"] for p in expected]
    response = client.post("/week3/discuss", json={
        "topic": "Dense versus sparse layers", "mode": "fake", "num_rounds": 3,
        "participant_ids": [p["id"] for p in personas[:2]],
    })
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert not any(e.get("event") == "discussion_failed" for e in events), response.text
    assert "event: discussion_completed" in response.text
    discussion_id = response.headers["x-discussion-id"]
    detail = client.get(f"/discussions/{discussion_id}").json()
    assert detail["status"] == "completed"
    assert len(detail["messages"]) == 9  # 2 openings, 6 responses, moderator
    assert {m["round_number"] for m in detail["messages"] if m["phase"] == "discussion"} == {1, 2, 3}
    assert client.get("/discussions").json()[0]["discussion_id"] == discussion_id
    assert (config.WEEK3_OUTPUT_DIR / f"{discussion_id}.jsonl").is_file()


def test_cached_cli_analytics_and_artifacts(client):
    discussion_id = "saved-live-discussion"
    result = {"discussion_id": discussion_id, "opinion_change": [], "agreement": {},
              "influence": {}, "sentiment": {}}
    config.ANALYTICS_OUT_DIR.mkdir(parents=True)
    analytics_runner.cached_result_path(discussion_id).write_text(json.dumps(result))
    analytics_runner.report_path(discussion_id).write_text("# Saved report", encoding="utf-8")
    config.ANALYTICS_VISUALS_DIR.mkdir()
    for path in analytics_runner.visual_paths(discussion_id).values():
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert client.get(f"/week4/analytics/{discussion_id}").json() == result
    stream = client.get(f"/week4/analytics/{discussion_id}/stream").text
    assert stream.count("event: metric_completed") == 6
    assert "event: analytics_completed" in stream
    assert client.get(f"/week4/report/{discussion_id}").text == "# Saved report"
    assert client.get(f"/week4/visuals/{discussion_id}/interaction_graph").status_code == 200
    assert client.get("/week4/analytics/missing").status_code == 404


def test_failures_are_streamed_and_persisted(client):
    response = client.post("/week3/discuss", json={
        "topic": "Example", "mode": "fake", "participant_ids": ["unknown", "other"],
    })
    assert "event: discussion_failed" in response.text
    discussion_id = response.headers["x-discussion-id"]
    assert client.get(f"/discussions/{discussion_id}").json()["status"] == "failed"
    assert client.get("/discussions/invalid%5Cid").status_code == 422


def test_json_and_stream_share_one_analytics_job(client, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = []

    def compute(discussion_id):
        calls.append(discussion_id)
        started.set()
        assert release.wait(5)
        return {"discussion_id": discussion_id}

    monkeypatch.setattr(analytics_runner, "_compute", compute)

    async def run():
        first = asyncio.create_task(analytics_runner.get_analytics("shared"))
        assert await asyncio.to_thread(started.wait, 5)
        second = asyncio.create_task(analytics_runner.get_analytics("shared"))
        await asyncio.sleep(0)
        release.set()
        assert await first == await second

    asyncio.run(run())
    assert calls == ["shared"]
