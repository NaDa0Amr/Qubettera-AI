"""Analytics for completed Qubettera discussion logs."""

from .loader import (
    DiscussionLog,
    OpinionSnapshot,
    discover_discussion_files,
    load_discussion,
)
from .opinion_change import (
    rows_by_agent,
    track_opinion_change,
    track_opinion_change_batch,
)
from .agreement import measure_agreement
from .influence import calculate_influence
from .sentiment import (
    SentimentResult,
    SentimentScorer,
    aggregate_by_agent,
    aggregate_by_round,
    score_sentiment,
    sentiment_distribution,
    truncation_summary,
)

__all__ = [
    # Loader
    "DiscussionLog",
    "OpinionSnapshot",
    "discover_discussion_files",
    "load_discussion",
    # Task 1
    "rows_by_agent",
    "track_opinion_change",
    "track_opinion_change_batch",
    # Task 2
    "measure_agreement",
    # Task 3
    "calculate_influence",
    # Task 4
    "SentimentResult",
    "SentimentScorer",
    "aggregate_by_agent",
    "aggregate_by_round",
    "score_sentiment",
    "sentiment_distribution",
    "truncation_summary",
]

