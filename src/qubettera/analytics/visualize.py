"""Generate PNG charts from a completed analytics result."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
from PIL import Image, ImageDraw, ImageFont


_COLORS = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#d97706", "#0891b2"]


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _validate_analytics(analytics: dict[str, Any]) -> None:
    if not isinstance(analytics, dict) or not all(
        key in analytics for key in ("discussion_id", "agent_ids", "rounds", "opinion_change", "edges")
    ):
        raise ValueError("Analytics result is missing chart inputs")


def load_analytics_json(path: str | Path) -> dict[str, Any]:
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_analytics(result)
    return result


def plot_opinion_trajectory(analytics: dict[str, Any], output_path: str | Path, *, dpi: int = 180) -> Path:
    """Draw every participant's stance over available discussion rounds."""
    _validate_analytics(analytics)
    rounds = sorted(set(analytics["rounds"]))
    if not rounds:
        raise ValueError("No discussion rounds to plot")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 720), "white")
    draw = ImageDraw.Draw(image)
    plot_left, plot_top, plot_right, plot_bottom = 95, 75, 930, 615
    title_font, label_font = _font(25), _font(17)
    draw.text((95, 20), "Opinion trajectory", fill="#111827", font=title_font)
    for value in (-1, -0.5, 0, 0.5, 1):
        y = plot_bottom - (value + 1) / 2 * (plot_bottom - plot_top)
        draw.line((plot_left, y, plot_right, y), fill="#e5e7eb", width=2)
        draw.text((35, y - 10), f"{value:+.1f}", fill="#374151", font=label_font)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill="#111827", width=3)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#111827", width=3)
    x_for = lambda round_number: plot_left + (rounds.index(round_number) / max(1, len(rounds) - 1)) * (plot_right - plot_left)
    y_for = lambda stance: plot_bottom - (float(stance) + 1) / 2 * (plot_bottom - plot_top)
    for round_number in rounds:
        x = x_for(round_number)
        draw.text((x - 5, plot_bottom + 12), str(round_number), fill="#374151", font=label_font)
    by_agent: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for row in analytics["opinion_change"]:
        by_agent[str(row["agent_id"])].append((int(row["round"]), float(row["stance"])))
    for index, agent in enumerate(analytics["agent_ids"]):
        color = _COLORS[index % len(_COLORS)]
        points = [(x_for(r), y_for(s)) for r, s in sorted(by_agent.get(agent, [])) if r in rounds]
        if len(points) > 1:
            draw.line(points, fill=color, width=4)
        for x, y in points:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
        draw.line((965, 102 + 30 * index, 997, 102 + 30 * index), fill=color, width=4)
        draw.text((1005, 92 + 30 * index), str(agent), fill="#111827", font=label_font)
    draw.text((455, 665), "Discussion round", fill="#374151", font=label_font)
    image.save(output_path, dpi=(dpi, dpi))
    return output_path


def build_interaction_graph(analytics: dict[str, Any]) -> nx.DiGraph:
    """Keep declared nodes and routed edges with their edge-level estimates."""
    _validate_analytics(analytics)
    graph = nx.DiGraph()
    graph.add_nodes_from(analytics["agent_ids"])
    agent_scores = {row["agent_id"]: row.get("influence") for row in analytics.get("influence", [])}
    edge_scores = {(row["source"], row["target"]): row.get("influence") for row in analytics.get("influence_edges", [])}
    for source, target in analytics["edges"]:
        if source not in graph or target not in graph:
            raise ValueError("Interaction edge references an unknown participant")
        score = edge_scores.get((source, target), agent_scores.get(source))
        graph.add_edge(source, target, source_influence=score,
                       visual_weight=1 + 4 * abs(score or 0))
    return graph


def plot_interaction_graph(analytics: dict[str, Any], output_path: str | Path, *, dpi: int = 180) -> Path:
    """Draw all participants and directed message routes with signed scores."""
    graph = build_interaction_graph(analytics)
    if not graph.nodes:
        raise ValueError("No agents to plot")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(image)
    title_font, label_font = _font(25), _font(17)
    draw.text((70, 20), "Agent interactions and estimated influence", fill="#111827", font=title_font)
    positions = nx.circular_layout(graph)
    coords = {node: (int(600 + xy[0] * 380), int(405 + xy[1] * 280)) for node, xy in positions.items()}
    for source, target, data in graph.edges(data=True):
        sx, sy = coords[source]
        tx, ty = coords[target]
        if source == target:
            continue
        dx, dy = tx - sx, ty - sy
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        # Offset reciprocal routes so both directed edges remain visible.
        offset = 22
        px, py = -uy * offset, ux * offset
        start = (sx + ux * 55 + px, sy + uy * 55 + py)
        end = (tx - ux * 55 + px, ty - uy * 55 + py)
        draw.line((start, end), fill="#64748b", width=int(data["visual_weight"] + 1))
        draw.polygon([end, (end[0] - ux * 16 - uy * 7, end[1] - uy * 16 + ux * 7),
                      (end[0] - ux * 16 + uy * 7, end[1] - uy * 16 - ux * 7)], fill="#64748b")
        value = data["source_influence"]
        label = "n/a" if value is None else f"{value:+.2f}"
        draw.text(((start[0] + end[0]) / 2, (start[1] + end[1]) / 2), label,
                  fill="#111827", font=label_font)
    for node, (x, y) in coords.items():
        draw.ellipse((x - 53, y - 53, x + 53, y + 53), fill="#dbeafe", outline="#2563eb", width=3)
        label = str(node).replace("_", " ")
        box = draw.textbbox((0, 0), label, font=label_font)
        draw.text((x - (box[2] - box[0]) / 2, y - 9), label, fill="#111827", font=label_font)
    draw.text((70, 752), "Edge width and label show the estimated association; n/a means insufficient data.",
              fill="#374151", font=label_font)
    image.save(output_path, dpi=(dpi, dpi))
    return output_path


def create_visualizations(analytics: dict[str, Any], output_dir: str | Path = "visuals", *, dpi: int = 180) -> dict[str, Path]:
    """Write the stance chart and interaction graph under a predictable name."""
    output_dir = Path(output_dir)
    discussion_id = str(analytics["discussion_id"])
    return {
        "opinion_trajectory": plot_opinion_trajectory(analytics, output_dir / f"opinion_trajectory_{discussion_id}.png", dpi=dpi),
        "interaction_graph": plot_interaction_graph(analytics, output_dir / f"interaction_graph_{discussion_id}.png", dpi=dpi),
    }
