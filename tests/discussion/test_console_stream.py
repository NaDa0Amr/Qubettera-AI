"""ConsoleTurnStream must show progress live and still delegate every write."""

import json

from qubettera.discussion.console_stream import ConsoleTurnStream, resolve_persona_names
from qubettera.discussion.interfaces import NullEventSink


class RecordingSink:
    def __init__(self):
        self.events = []

    def write_event(self, event):
        self.events.append(event)


def _turn(sender_id="dr_aris", phase="discussion", round_number=1, **overrides):
    message = {
        "sender_id": sender_id,
        "phase": phase,
        "round_number": round_number,
        "recipient_ids": ["prof_elena"],
        "opinion": "Dense layers are simpler but MoE wins on FLOPs.",
        "retrieval_query": "mixture of experts efficiency",
        "evidence": [{"text": "t"}],
    }
    message.update(overrides)
    return {"event": "turn_completed", "message": message}


def test_every_event_is_forwarded_to_the_wrapped_sink(capsys):
    sink = RecordingSink()
    stream = ConsoleTurnStream(sink, {})

    stream.write_event({"event": "discussion_started", "config": {"participant_ids": ["a", "b"], "num_rounds": 3}})
    stream.write_event(_turn())
    stream.write_event({"event": "discussion_completed", "message_count": 20})

    assert [event["event"] for event in sink.events] == [
        "discussion_started",
        "turn_completed",
        "discussion_completed",
    ]


def test_printing_never_depends_on_the_sink(capsys):
    """A NullEventSink (used by tests and library callers) still streams to stdout."""
    stream = ConsoleTurnStream(NullEventSink(), {"dr_aris": "Dr. Aris Thorne"})
    stream.write_event(_turn())

    out = capsys.readouterr().out
    assert "[round 1] Dr. Aris Thorne (dr_aris) -> prof_elena" in out
    assert "[retrieval] mixture of experts efficiency" in out
    assert "[evidence] 1 item(s)" in out


def test_initial_phase_is_labelled_as_opening(capsys):
    stream = ConsoleTurnStream(NullEventSink(), {})
    stream.write_event(_turn(phase="initial", round_number=0))

    assert "[opening]" in capsys.readouterr().out


def test_recipients_fall_back_to_nobody(capsys):
    stream = ConsoleTurnStream(NullEventSink(), {})
    stream.write_event(_turn(recipient_ids=[]))

    assert "(nobody)" in capsys.readouterr().out


def test_long_opinion_and_query_are_truncated(capsys):
    stream = ConsoleTurnStream(NullEventSink(), {})
    stream.write_event(
        _turn(opinion="x" * 900, retrieval_query="q" * 300)
    )

    out = capsys.readouterr().out
    assert "x" * stream.OPINION_LIMIT in out
    assert "x" * (stream.OPINION_LIMIT + 1) not in out
    assert "q" * stream.QUERY_LIMIT in out
    assert "q" * (stream.QUERY_LIMIT + 1) not in out


def test_failure_event_surfaces_the_reason(capsys):
    """The orchestrator raises right after this event, so the reason must print here."""
    stream = ConsoleTurnStream(NullEventSink(), {})
    stream.write_event(
        {
            "event": "discussion_failed",
            "error": "RuntimeError: model unavailable",
            "completed_message_count": 7,
        }
    )

    out = capsys.readouterr().out
    assert "RuntimeError: model unavailable" in out
    assert "7" in out


def test_resolve_persona_names_maps_known_ids_to_real_names():
    names = resolve_persona_names(("dr_aris", "prof_elena"))

    assert names["dr_aris"] == "Dr. Aris Thorne"
    assert names["prof_elena"] == "Prof. Elena Vance"


def test_resolve_persona_names_covers_the_configured_debate_team():
    """The default discussion.json roster must all resolve to display names."""
    from qubettera.discussion.config import load_discussion_config
    from qubettera.paths import CONFIGS_DIR

    config = load_discussion_config(CONFIGS_DIR / "discussion.json")
    names = resolve_persona_names(config.participant_ids)

    assert all(name != agent_id for agent_id, name in names.items())


def test_resolve_persona_names_falls_back_for_unknown_ids():
    names = resolve_persona_names(("not_a_real_persona",))

    assert names == {"not_a_real_persona": "not_a_real_persona"}


def test_resolve_persona_names_reads_files_from_the_real_personas_dir():
    """Regression: the old lookup used a relative personas/ path that never existed."""
    names = resolve_persona_names(("dr_aris",))

    assert names["dr_aris"] != "dr_aris"


def test_stream_writes_valid_json_through_to_a_jsonl_sink(tmp_path):
    from qubettera.discussion.run_log import JsonlEventSink

    path = tmp_path / "log.jsonl"
    stream = ConsoleTurnStream(JsonlEventSink(path), {})
    stream.write_event(_turn())

    (line,) = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["message"]["sender_id"] == "dr_aris"
