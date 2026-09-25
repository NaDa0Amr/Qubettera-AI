"""`qubettera discuss run` must stream to the console and name its log meaningfully."""

import json
import re

from qubettera import cli


def _run_fake_discussion(tmp_path, extra_args=()):
    args = [
        "discuss",
        "run",
        "--mode",
        "fake",
        "--output-dir",
        str(tmp_path),
        *extra_args,
    ]
    return cli.main(args)


def test_cli_streams_turns_to_stdout(capsys, tmp_path):
    """Regression: the CLI used to write a bare JsonlEventSink and print nothing."""
    assert _run_fake_discussion(tmp_path) == 0

    out = capsys.readouterr().out
    assert "[opening]" in out
    for round_number in (1, 2, 3):
        assert f"[round {round_number}]" in out


def test_cli_prints_status_and_log_path(capsys, tmp_path):
    assert _run_fake_discussion(tmp_path) == 0

    out = capsys.readouterr().out
    assert "completed" in out
    assert "Event log:" in out


def test_cli_uses_persona_display_names_not_raw_ids(capsys, tmp_path):
    assert _run_fake_discussion(tmp_path) == 0

    out = capsys.readouterr().out
    assert "Dr. Aris Thorne" in out


def test_cli_writes_a_meaningful_filename(tmp_path):
    assert _run_fake_discussion(tmp_path) == 0

    (log_path,) = list(tmp_path.glob("*.jsonl"))
    assert re.fullmatch(
        r"fake-5agents-3rounds-\d{8}T\d{6}-[a-z0-9]+\.jsonl",
        log_path.name,
    )


def test_cli_filename_is_not_a_bare_uuid(tmp_path):
    assert _run_fake_discussion(tmp_path) == 0

    (log_path,) = list(tmp_path.glob("*.jsonl"))
    assert not re.fullmatch(r"[0-9a-f\-]{36}\.jsonl", log_path.name)


def test_cli_written_log_still_contains_the_full_discussion_id(tmp_path):
    """The shortened filename must not cost traceability."""
    assert _run_fake_discussion(tmp_path) == 0

    (log_path,) = list(tmp_path.glob("*.jsonl"))
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    short_id = log_path.name.split("-")[-1].removesuffix(".jsonl")

    assert events[0]["event"] == "discussion_started"
    assert events[0]["discussion_id"].startswith(short_id)


def test_cli_log_records_every_turn(capsys, tmp_path):
    assert _run_fake_discussion(tmp_path) == 0
    capsys.readouterr()

    (log_path,) = list(tmp_path.glob("*.jsonl"))
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert sum(event["event"] == "turn_completed" for event in events) == 20
    assert events[-1]["event"] == "discussion_completed"


def test_cli_no_retrieval_flag_still_streams(capsys, tmp_path):
    assert _run_fake_discussion(tmp_path, ("--no-retrieval",)) == 0

    assert "[round 1]" in capsys.readouterr().out
