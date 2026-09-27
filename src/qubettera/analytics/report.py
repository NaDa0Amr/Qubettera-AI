"""Render analytics as a Markdown report."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .engine import get_analytics

if TYPE_CHECKING:
    from .report_agent import ReportAgent, ReportNarrative
    from .sentiment import SentimentScorer
    from .stance_scorer import StanceScorer


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPINION_TRAJECTORY_KEY = "opinion_trajectory"
_INTERACTION_GRAPH_KEY = "interaction_graph"
_EXPECTED_VISUALS: tuple[tuple[str, str], ...] = (
    (_OPINION_TRAJECTORY_KEY, "opinion_trajectory.png"),
    (_INTERACTION_GRAPH_KEY, "interaction_graph.png"),
)

_CELL_TRUNCATE = 120


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_float(value: float | None, precision: int = 4, signed: bool = True) -> str:
    """Format an optional float for display, or em-dash when None."""
    if value is None:
        return "â€”"
    if signed:
        return f"{value:+.{precision}f}"
    return f"{value:.{precision}f}"


def _fmt_pct(count: int, total: int) -> str:
    """Format a percentage with one decimal place, or em-dash when total is 0."""
    if total <= 0:
        return "â€”"
    return f"{count / total * 100:.1f}%"


def _escape_cell(value: Any) -> str:
    """Escape a value for safe inclusion in a Markdown table cell."""
    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    if len(text) > _CELL_TRUNCATE:
        text = text[: _CELL_TRUNCATE - 1] + "â€¦"
    return text


def _short_message_id(message_id: str) -> str:
    """Shorten a `<discussion_id>:<sequence>` message ID for compact display."""
    if not message_id:
        return "â€”"
    if ":" in message_id:
        return "â€¦" + message_id.split(":")[-1]
    return message_id[-8:] if len(message_id) > 8 else message_id


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(analytics: dict[str, Any]) -> str:
    meta = analytics.get("metadata", {})
    sentiment_model = (
        meta.get("sentiment_model")
        or analytics.get("sentiment", {}).get("method")
        or "unknown"
    )
    stance_model = meta.get("stance_model") or (
        "cache" if meta.get("task1_from_cache") else "unknown"
    )

    lines = [
        "# Discussion Analytics Report",
        "",
        f"> **Discussion ID:** `{analytics.get('discussion_id', 'â€”')}`",
        f"> **Generated:** {meta.get('generated_at', 'â€”')}",
        f"> **Stance model:** `{stance_model}`",
        f"> **Sentiment model:** `{sentiment_model}`",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _render_overview(analytics: dict[str, Any]) -> str:
    lines = ["## 1. Discussion Overview", ""]

    objective = analytics.get("objective", "")
    if objective:
        lines.append(f"**Objective:** {objective}")
        lines.append("")

    proposition = analytics.get("proposition", "")
    if proposition:
        lines.append(f"**Proposition:** {proposition}")
        lines.append("")

    agents = analytics.get("agent_ids", [])
    rounds = analytics.get("rounds", [])
    edges = analytics.get("edges", [])

    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(
        f"| Agents | {len(agents)}: "
        f"{', '.join(f'`{a}`' for a in agents) or 'â€”'} |"
    )
    lines.append(
        f"| Rounds | {len(rounds)}: "
        f"{', '.join(str(r) for r in rounds) or 'â€”'} |"
    )
    lines.append(f"| Communication edges | {len(edges)} |")
    lines.append("")

    topics = analytics.get("topics", [])
    if topics:
        lines.append("**Topics under debate:**")
        lines.append("")
        for t in topics:
            lines.append(f"- {t}")
        lines.append("")

    return "\n".join(lines)


def _render_opinion_dynamics(
    analytics: dict[str, Any],
    narrative: "ReportNarrative | None",
) -> str:
    lines = ["## 2. Opinion Dynamics", ""]
    rows = analytics.get("opinion_change", [])
    if not rows:
        lines.append("*No opinion-change rows were produced for this discussion.*")
        lines.append("")
        return "\n".join(lines)

    if narrative is not None:
        lines.append(narrative.opinion_analysis)
        lines.append("")

    lines.append("### Stance Trajectory")
    lines.append("")
    lines.append("| Agent | Round | Stance | Change |")
    lines.append("|---|---:|---:|---:|")
    for r in sorted(rows, key=lambda x: (x["agent_id"], x["round"])):
        lines.append(
            f"| `{_escape_cell(r['agent_id'])}` "
            f"| {r['round']} "
            f"| {_fmt_float(r['stance'])} "
            f"| {_fmt_float(r.get('change'))} |"
        )
    lines.append("")

    by_agent: dict[str, list[dict]] = {}
    for r in rows:
        by_agent.setdefault(r["agent_id"], []).append(r)

    lines.append("### Per-Agent Summary")
    lines.append("")
    lines.append("| Agent | Initial | Final | Net Change | Total Movement |")
    lines.append("|---|---:|---:|---:|---:|")
    for agent, agent_rows in sorted(by_agent.items()):
        agent_rows.sort(key=lambda x: x["round"])
        initial = agent_rows[0]["stance"]
        final = agent_rows[-1]["stance"]
        net = round(final - initial, 4)
        total = round(
            sum(abs(r["change"]) for r in agent_rows if r.get("change") is not None),
            4,
        )
        lines.append(
            f"| `{_escape_cell(agent)}` "
            f"| {_fmt_float(initial)} "
            f"| {_fmt_float(final)} "
            f"| {_fmt_float(net)} "
            f"| {total:.4f} |"
        )
    lines.append("")

    return "\n".join(lines)


def _render_agreement(
    analytics: dict[str, Any],
    narrative: "ReportNarrative | None",
) -> str:
    lines = ["## 3. Agreement / Disagreement", ""]
    agreement = analytics.get("agreement", [])
    if not agreement:
        lines.append("*No agreement scores were produced for this discussion.*")
        lines.append("")
        return "\n".join(lines)

    if narrative is not None:
        lines.append(narrative.agreement_analysis)
        lines.append("")

    lines.append("| Round | Agreement | Agents Present | Note |")
    lines.append("|---:|---:|---:|---|")
    for a in agreement:
        lines.append(
            f"| {a['round']} "
            f"| {_fmt_float(a.get('agreement'))} "
            f"| {a['n_agents']} | {_escape_cell(a.get('note') or '')} |"
        )
    lines.append("")

    scored_agreement = [a for a in agreement if a.get("agreement") is not None]
    if len(scored_agreement) >= 2:
        first = scored_agreement[0]["agreement"]
        last = scored_agreement[-1]["agreement"]
        delta = last - first
        if delta > 0.05:
            trend = (
                f"Agreement **rose** from {first:.4f} to {last:.4f} "
                f"(net +{delta:.4f}), suggesting the group converged."
            )
        elif delta < -0.05:
            trend = (
                f"Agreement **fell** from {first:.4f} to {last:.4f} "
                f"(net {delta:+.4f}), suggesting the group polarised."
            )
        else:
            trend = (
                f"Agreement was **stable** across the discussion "
                f"(first {first:.4f}, last {last:.4f}, net {delta:+.4f})."
            )
        lines.append(f"**Trend:** {trend}")
        lines.append("")
    else:
        lines.append("*Fewer than two scored rounds are available; no trend can be inferred.*")
        lines.append("")

    return "\n".join(lines)


def _render_influence(
    analytics: dict[str, Any],
    narrative: "ReportNarrative | None",
) -> str:
    lines = ["## 4. Influence", ""]
    influence = analytics.get("influence", [])
    if not influence:
        lines.append("*No influence scores were produced for this discussion.*")
        lines.append("")
        return "\n".join(lines)

    if narrative is not None:
        lines.append(narrative.influence_analysis)
        lines.append("")

    lines.append("| Agent | Influence | Note |")
    lines.append("|---|---:|---|")
    for i in influence:
        note = _escape_cell(i.get("note") or "")
        lines.append(
            f"| `{_escape_cell(i['agent_id'])}` "
            f"| {_fmt_float(i.get('influence'))} "
            f"| {note} |"
        )
    lines.append("")

    scored = [i for i in influence if i.get("influence") is not None]
    if scored:
        highest = max(scored, key=lambda x: x["influence"])
        lowest = min(scored, key=lambda x: x["influence"])
        lines.append(
            f"**Highest estimated influence:** `{highest['agent_id']}` "
            f"({_fmt_float(highest['influence'])})"
        )
        lines.append(
            f"**Lowest estimated influence:** `{lowest['agent_id']}` "
            f"({_fmt_float(lowest['influence'])})"
        )
        lines.append("")
    else:
        lines.append(
            "*Influence could not be estimated for any agent â€” typically because "
            "the discussion had too few routed transitions or too little "
            "stance variation for correlation.*"
        )
        lines.append("")

    lines.append(
        "> **Interpretation caveat:** Scores combine stance-gap correlation "
        "with message-term overlap. They measure *association*, not causation. "
        "A high score does not prove that an agent convinced others."
    )
    lines.append("")

    return "\n".join(lines)


def _render_sentiment(
    analytics: dict[str, Any],
    narrative: "ReportNarrative | None",
) -> str:
    lines = ["## 5. Sentiment", ""]
    sentiment = analytics.get("sentiment", {})
    messages = sentiment.get("messages", [])
    if not messages:
        lines.append("*No sentiment scores were produced for this discussion.*")
        lines.append("")
        return "\n".join(lines)

    lines.append(
        "Sentiment measures the **emotional tone** of each message on a "
        "continuous scale from `-1.0` (strongly negative) to `+1.0` "
        "(strongly positive). It is independent of stance â€” an agent can hold "
        "a strong position while expressing it in neutral, evidence-based prose."
    )
    lines.append("")

    if narrative is not None:
        lines.append(narrative.sentiment_analysis)
        lines.append("")

    dist = sentiment.get("distribution", {})
    total = sum(dist.values()) or 1
    lines.append("### Distribution")
    lines.append("")
    lines.append("| Label | Count | Share |")
    lines.append("|---|---:|---:|")
    for label in ("positive", "neutral", "negative"):
        count = dist.get(label, 0)
        lines.append(f"| {label.capitalize()} | {count} | {_fmt_pct(count, total)} |")
    lines.append("")

    by_agent = sentiment.get("by_agent", {})
    if by_agent:
        lines.append("### Per-Agent Average Sentiment")
        lines.append("")
        lines.append("| Agent | Avg Sentiment | Messages |")
        lines.append("|---|---:|---:|")
        for agent, data in sorted(
            by_agent.items(), key=lambda kv: -kv[1]["avg_sentiment"]
        ):
            lines.append(
                f"| `{_escape_cell(agent)}` "
                f"| {_fmt_float(data['avg_sentiment'])} "
                f"| {data['message_count']} |"
            )
        lines.append("")

    by_round = sentiment.get("by_round", {})
    if by_round:
        lines.append("### Per-Round Average Sentiment")
        lines.append("")
        lines.append("| Round | Avg Sentiment | Messages |")
        lines.append("|---:|---:|---:|")
        for rnd, data in by_round.items():
            lines.append(
                f"| {rnd} "
                f"| {_fmt_float(data['avg_sentiment'])} "
                f"| {data['message_count']} |"
            )
        lines.append("")

    if len(by_round) >= 2:
        sorted_rounds = sorted(by_round.items())
        first = sorted_rounds[0][1]["avg_sentiment"]
        last = sorted_rounds[-1][1]["avg_sentiment"]
        delta = last - first
        if delta > 0.05:
            trend = (
                f"Average tone **became more positive** across the discussion "
                f"({first:+.4f} â†’ {last:+.4f})."
            )
        elif delta < -0.05:
            trend = (
                f"Average tone **became more negative** across the discussion "
                f"({first:+.4f} â†’ {last:+.4f})."
            )
        else:
            trend = (
                f"Average tone was **stable** across the discussion "
                f"({first:+.4f} â†’ {last:+.4f})."
            )
        lines.append(f"**Trend:** {trend}")
        lines.append("")

    return "\n".join(lines)


def _render_key_findings(
    analytics: dict[str, Any],
    narrative: "ReportNarrative | None",
) -> str:
    lines = ["## 6. Key Findings", ""]
    if narrative is not None and narrative.key_findings:
        findings = list(narrative.key_findings)
    else:
        findings = _compute_findings(analytics)
    for finding in findings:
        lines.append(f"- {finding}")
    lines.append("")
    return "\n".join(lines)


def _render_executive_summary(narrative: "ReportNarrative") -> str:
    return "\n".join([
        "## Executive Summary",
        "",
        narrative.executive_summary,
        "",
    ])


def _render_conclusion(narrative: "ReportNarrative") -> str:
    return "\n".join([
        "## Conclusion",
        "",
        narrative.conclusion,
        "",
    ])


# ---------------------------------------------------------------------------
# Deterministic findings
# ---------------------------------------------------------------------------

def _compute_findings(analytics: dict[str, Any]) -> list[str]:
    """Derive a short list of hedged, falsifiable observations from the analytics."""
    findings: list[str] = []

    rows = analytics.get("opinion_change", [])
    by_agent: dict[str, list[dict]] = {}
    for r in rows:
        by_agent.setdefault(r["agent_id"], []).append(r)

    movements: list[tuple[str, float]] = []
    for agent, agent_rows in by_agent.items():
        if len(agent_rows) < 2:
            continue
        agent_rows = sorted(agent_rows, key=lambda x: x["round"])
        net = agent_rows[-1]["stance"] - agent_rows[0]["stance"]
        movements.append((agent, net))

    if movements:
        most_moved = max(movements, key=lambda x: abs(x[1]))
        if abs(most_moved[1]) > 0.01:
            direction = "toward" if most_moved[1] > 0 else "away from"
            findings.append(
                f"`{most_moved[0]}` showed the largest net stance movement "
                f"({most_moved[1]:+.4f}), moving {direction} the proposition."
            )
        else:
            findings.append(
                "All agents held their initial stances with negligible net movement."
            )

    agreement = [a for a in analytics.get("agreement", []) if a.get("agreement") is not None]
    if len(agreement) >= 2:
        most_aligned = max(agreement, key=lambda a: a["agreement"])
        least_aligned = min(agreement, key=lambda a: a["agreement"])
        findings.append(
            f"The group was most aligned in round {most_aligned['round']} "
            f"(agreement = {most_aligned['agreement']:.4f}) and least aligned "
            f"in round {least_aligned['round']} "
            f"(agreement = {least_aligned['agreement']:.4f})."
        )

    scored_influence = [
        i for i in analytics.get("influence", []) if i.get("influence") is not None
    ]
    if scored_influence:
        top = max(scored_influence, key=lambda x: x["influence"])
        findings.append(
            f"`{top['agent_id']}` had the highest estimated influence "
            f"({top['influence']:+.4f}); its routed messages had the strongest "
            "estimated association with recipient stance movement."
        )
    elif analytics.get("influence"):
        findings.append(
            "Influence could not be estimated for any agent in this discussion "
            "(insufficient routed transitions or no stance variation)."
        )

    dist = analytics.get("sentiment", {}).get("distribution", {})
    total_msgs = sum(dist.values())
    if total_msgs > 0:
        dominant = max(dist, key=lambda k: dist[k])
        share = dist[dominant] / total_msgs * 100
        findings.append(
            f"The overall tonal character of the discussion was **{dominant}** â€” "
            f"{dist[dominant]} of {total_msgs} messages ({share:.0f}%) received "
            f"the `{dominant}` label."
        )

    return findings or [
        "No notable findings could be derived from the available data."
    ]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def _render_visualizations(visuals: dict[str, str] | None) -> str:
    """Render the Visualizations section from a {title: path} mapping."""
    if not visuals:
        return ""

    lines = ["## 7. Visualizations", ""]
    for title, rel_path in visuals.items():
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"![{title}]({rel_path})")
        lines.append("")
    return "\n".join(lines)


def _resolve_visuals(
    out_path: Path,
    visuals_dir: str | Path | None,
    discussion_id: str | None = None,
) -> dict[str, str] | None:
    """Build the {title: relative_path} mapping for existing visual files.

    Task 7 writes ``opinion_trajectory_<discussion_id>.png`` and
    ``interaction_graph_<discussion_id>.png``. Older or manually produced
    files may use the generic names ``opinion_trajectory.png`` and
    ``interaction_graph.png``. This function tries the suffixed name first
    (using the discussion_id from the analytics dict), then the generic
    name, and returns the first one that exists.

    Returns None when `visuals_dir` is None, is not a directory, or contains
    no matching files.
    """
    if visuals_dir is None:
        return None
    visuals_dir = Path(visuals_dir)
    if not visuals_dir.is_dir():
        return None

    resolved: dict[str, str] = {}
    for key, base_filename in _EXPECTED_VISUALS:
        candidates: list[Path] = []
        if discussion_id:
            # Split "opinion_trajectory.png" into ("opinion_trajectory", ".png")
            stem, _, ext = base_filename.rpartition(".")
            candidates.append(visuals_dir / f"{stem}_{discussion_id}.{ext}")
        candidates.append(visuals_dir / base_filename)

        candidate = next((c for c in candidates if c.is_file()), None)
        if candidate is None:
            continue

        title = key.replace("_", " ").title()
        try:
            rel = candidate.resolve().relative_to(out_path.parent.resolve())
            rel_str = str(rel).replace("\\", "/")
        except ValueError:
            import os
            rel_str = os.path.relpath(
                candidate.resolve(), out_path.parent.resolve()
            )
            rel_str = rel_str.replace("\\", "/")
        resolved[title] = rel_str

    return resolved or None


# ---------------------------------------------------------------------------
# Limitations
# ---------------------------------------------------------------------------

def _render_limitations() -> str:
    return "\n".join(
        [
            "## 8. Limitations",
            "",
            "**Opinion change.** Stance scores are produced by an LLM and may "
            "misjudge mixed or ambiguous opinions even at temperature 0. The "
            "score is measured against a single bipolar proposition derived "
            "from the first `versus` topic; multi-axis debates are scored on "
            "one axis only.",
            "",
            "**Agreement.** Mean pairwise stance distance measures how *tight* the stances are, "
            "not *where* on the scale consensus lies. A round where all agents "
            "are at `+0.5` scores identically to a round where all agents are "
            "at `-0.5`.",
            "",
            "**Influence.** Scores combine correlation between prior stance gaps "
            "and later recipient movement with message-term overlap. They are "
            "observational associations, not proof of persuasion. Three usable "
            "transitions with variation are required; otherwise scores are `null`.",
            "",
            "**Sentiment.** The prototype model is trained on developer "
            "interactions rather than AI architecture debates, so it may "
            "under-detect sentiment in technical advocacy. It measures tone, "
            "not agreement; a strongly positive score does not imply support "
            "for the proposition.",
            "",
            "**Cross-metric caveats.** None of the metrics here measure "
            "correctness, persuasiveness, or decision quality. A group that "
            "reaches high agreement on a wrong answer scores identically to "
            "one that reaches consensus on the right answer.",
            "",
        ]
    )


# ---------------------------------------------------------------------------
# Public API â€” deterministic render
# ---------------------------------------------------------------------------

def render_report(
    analytics: dict[str, Any],
    *,
    visuals: dict[str, str] | None = None,
    narrative: "ReportNarrative | None" = None,
) -> str:
    """Render the full Markdown report as a string."""
    sections: list[str] = [_render_header(analytics)]

    if narrative is not None:
        sections.append(_render_executive_summary(narrative))

    sections.extend([
        _render_overview(analytics),
        _render_opinion_dynamics(analytics, narrative),
        _render_agreement(analytics, narrative),
        _render_influence(analytics, narrative),
        _render_sentiment(analytics, narrative),
        _render_key_findings(analytics, narrative),
    ])

    if narrative is not None:
        sections.append(_render_conclusion(narrative))

    visuals_section = _render_visualizations(visuals)
    if visuals_section:
        sections.append(visuals_section)

    sections.append(_render_limitations())
    return "\n".join(sections)


def write_report(
    analytics: dict[str, Any],
    out_path: str | Path,
    *,
    visuals_dir: str | Path | None = None,
    visuals: dict[str, str] | None = None,
    narrative: "ReportNarrative | None" = None,
) -> Path:
    """Write the Markdown report to ``out_path`` and return the path.

    When `visuals` is not explicitly provided, `visuals_dir` is scanned for
    the discussion's PNG files. Task 7's suffixed filenames are looked up
    first, then the generic unsuffixed names.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if visuals is None:
        visuals = _resolve_visuals(
            out_path,
            visuals_dir,
            discussion_id=analytics.get("discussion_id"),
        )

    markdown = render_report(analytics, visuals=visuals, narrative=narrative)
    out_path.write_text(markdown, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Public API â€” end-to-end deterministic path
# ---------------------------------------------------------------------------

def generate_report(
    discussion_path: str | Path,
    out_path: str | Path,
    *,
    stance_scorer: "StanceScorer | None" = None,
    sentiment_scorer: "SentimentScorer | None" = None,
    task1_result: dict[str, Any] | None = None,
    visuals_dir: str | Path | None = None,
    visuals: dict[str, str] | None = None,
) -> Path:
    """End-to-end convenience: run the engine, render, and write the report."""
    analytics = get_analytics(
        discussion_path,
        stance_scorer=stance_scorer,
        sentiment_scorer=sentiment_scorer,
        task1_result=task1_result,
    )
    return write_report(
        analytics,
        out_path,
        visuals_dir=visuals_dir,
        visuals=visuals,
    )


# ---------------------------------------------------------------------------
# Public API â€” agent path
# ---------------------------------------------------------------------------

def write_agent_report(
    analytics: dict[str, Any],
    out_path: str | Path,
    *,
    agent: "ReportAgent | None" = None,
    visuals_dir: str | Path | None = None,
    visuals: dict[str, str] | None = None,
) -> Path:
    """Render a report with an LLM narrative and write it to disk."""
    from .report_agent import ReportAgent

    if agent is None:
        agent = ReportAgent()

    narrative = agent.generate(analytics)
    return write_report(
        analytics,
        out_path,
        visuals_dir=visuals_dir,
        visuals=visuals,
        narrative=narrative,
    )


def generate_agent_report(
    discussion_path: str | Path,
    out_path: str | Path,
    *,
    agent: "ReportAgent | None" = None,
    stance_scorer: "StanceScorer | None" = None,
    sentiment_scorer: "SentimentScorer | None" = None,
    task1_result: dict[str, Any] | None = None,
    visuals_dir: str | Path | None = None,
    visuals: dict[str, str] | None = None,
) -> Path:
    """End-to-end agent path: engine â†’ agent â†’ report â†’ write."""
    analytics = get_analytics(
        discussion_path,
        stance_scorer=stance_scorer,
        sentiment_scorer=sentiment_scorer,
        task1_result=task1_result,
    )
    return write_agent_report(
        analytics,
        out_path,
        agent=agent,
        visuals_dir=visuals_dir,
        visuals=visuals,
    )

