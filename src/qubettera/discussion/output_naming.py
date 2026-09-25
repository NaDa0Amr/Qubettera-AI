"""Meaningful, scan-friendly filenames for discussion event logs.

Bare UUID filenames are impossible to identify at a glance, so both the CLI and
the demo build their log names from the run's identifying information: the mode,
the number of agents and rounds, a sortable UTC timestamp, and a short prefix of
the discussion UUID. The debate objective is deliberately left out - it is long,
differs between runs that share a configuration, and is already recorded inside
the log. The full UUID is stored there as ``discussion_id``, so traceability is
not lost.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

SLUG_MAX_LENGTH = 60
UUID_PREFIX_LENGTH = 8
FALLBACK_SLUG = "discussion"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = SLUG_MAX_LENGTH) -> str:
    """Reduce free text to a lowercase, dash-separated filename fragment."""
    slug = _NON_ALNUM.sub("-", text.lower()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length]
        # Prefer a word boundary so a truncated slug stays readable, unless
        # that would drop a whole word.
        if "-" in slug:
            head = slug.rpartition("-")[0]
            if head:
                slug = head
        slug = slug.rstrip("-")
    return slug or FALLBACK_SLUG


def utc_timestamp(moment: datetime | None = None) -> str:
    """Return a compact, lexicographically sortable UTC timestamp."""
    return (moment or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S")


def discussion_log_filename(
    *,
    mode: str,
    num_agents: int,
    num_rounds: int,
    discussion_id: str,
    moment: datetime | None = None,
    prefix: str = "",
) -> str:
    """Build the event-log filename for one discussion run."""
    stamped = utc_timestamp(moment)
    short_id = slugify(discussion_id, max_length=UUID_PREFIX_LENGTH)
    stem = (
        f"{prefix}{mode}-{num_agents}agents-{num_rounds}rounds-"
        f"{stamped}-{short_id}"
    )
    return f"{stem}.jsonl"
