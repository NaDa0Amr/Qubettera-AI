"""Event-log filenames must be readable, sortable, and filesystem-safe."""

import re
from datetime import datetime, timezone

from qubettera.discussion.output_naming import (
    FALLBACK_SLUG,
    discussion_log_filename,
    slugify,
    utc_timestamp,
)

MOMENT = datetime(2026, 1, 14, 9, 30, 12, tzinfo=timezone.utc)
DISCUSSION_ID = "2c266cf1-bbd2-4f4b-b93b-b6b6a48c4ecc"


def _filename(**overrides):
    kwargs = {
        "mode": "live",
        "num_agents": 5,
        "num_rounds": 3,
        "discussion_id": DISCUSSION_ID,
        "moment": MOMENT,
    }
    kwargs.update(overrides)
    return discussion_log_filename(**kwargs)


def test_filename_follows_the_agreed_pattern():
    assert _filename() == "live-5agents-3rounds-20260114T093012-2c266cf1.jsonl"


def test_filename_components_appear_in_order():
    name = _filename()
    assert name.startswith("live-5agents-3rounds-")
    assert name.endswith("-20260114T093012-2c266cf1.jsonl")


def test_filename_is_sortable_by_timestamp():
    earlier = _filename(moment=datetime(2026, 1, 14, 9, 30, 11, tzinfo=timezone.utc))
    later = _filename(moment=datetime(2026, 1, 14, 9, 30, 12, tzinfo=timezone.utc))

    assert earlier < later


def test_filename_contains_no_path_separators_or_spaces():
    name = _filename()

    assert " " not in name
    assert "/" not in name
    assert "\\" not in name
    assert re.fullmatch(r"[a-z0-9T.\-]+", name)


def test_uuid_is_shortened_but_kept_traceable():
    name = _filename()

    assert "2c266cf1" in name
    assert DISCUSSION_ID not in name


def test_prefix_is_preserved_for_the_demo_entry_point():
    assert _filename(prefix="demo-").startswith("demo-live-5agents-3rounds-")


def test_objective_is_not_part_of_the_filename():
    # The objective was dropped to keep names short; nothing may sit between
    # the round count and the timestamp.
    name = _filename()
    assert re.fullmatch(
        r"live-5agents-3rounds-\d{8}T\d{6}-[a-z0-9]+\.jsonl", name
    )


def test_truncation_prefers_a_word_boundary():
    assert slugify("alpha bravo charlie delta", max_length=13) == "alpha-bravo"


def test_truncation_keeps_a_single_long_word_rather_than_emptying_the_slug():
    assert slugify("a" * 100, max_length=10) == "a" * 10


def test_slugify_normalizes_separators_and_case():
    assert slugify("  Dense   Layers / vs. MoE!! ") == "dense-layers-vs-moe"


def test_slugify_falls_back_when_nothing_survives():
    assert slugify("!!! ???") == FALLBACK_SLUG
    assert slugify("") == FALLBACK_SLUG


def test_slugify_truncation_strips_a_trailing_dash():
    assert not slugify("ab " * 40, max_length=5).endswith("-")


def test_timestamp_uses_utc_and_is_second_resolution():
    assert utc_timestamp(MOMENT) == "20260114T093012"
    assert re.fullmatch(r"\d{8}T\d{6}", utc_timestamp())
