"""The runnable qubettera.discussion.demo must stream the debate to the console in fake mode."""

import json
import sys

from qubettera.discussion import demo


def run_fake_demo(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        ["qubettera.discussion.demo", "--mode", "fake", "--output-dir", str(tmp_path)],
    )
    return demo.main()


def test_fake_mode_streams_every_turn(monkeypatch, capsys, tmp_path):
    assert run_fake_demo(monkeypatch, tmp_path) == 0

    out = capsys.readouterr().out
    assert "[opening]" in out
    for round_number in (1, 2, 3):
        assert f"[round {round_number}]" in out
    assert out.count("[round 1]") == len(
        json.loads((tmp_path / sorted(p.name for p in tmp_path.iterdir())[0]).read_text(encoding="utf-8").splitlines()[0])[
            "config"
        ]["participant_ids"]
    )
    assert "dr_aris" in out
    assert "prof_elena" in out


def test_fake_mode_logs_events_while_streaming(monkeypatch, capsys, tmp_path):
    assert run_fake_demo(monkeypatch, tmp_path) == 0

    log_path = next(tmp_path.glob("*.jsonl"))
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event"] == "discussion_started"
    assert events[-1]["event"] == "discussion_completed"
    assert sum(event["event"] == "turn_completed" for event in events) == 20