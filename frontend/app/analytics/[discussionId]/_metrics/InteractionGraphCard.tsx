"use client";

import Image from "next/image";
import { useState } from "react";
import { ImageOff } from "lucide-react";
import type { AnalyticsState } from "@/types";
import { getAgentColor } from "@/lib/palette";

interface VisualsData {
  opinion_trajectory_url: string | null;
  interaction_graph_url: string | null;
}

interface InteractionGraphCardProps {
  discussionId: string;
  visualsData: unknown;
  analyticsState: AnalyticsState;
}

function agentLabel(id: string) {
  return id.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export function InteractionGraphCard({
  discussionId,
  visualsData,
  analyticsState,
}: InteractionGraphCardProps) {
  const [imgError, setImgError] = useState(false);

  const data = visualsData as VisualsData | null;
  const graphUrl = `/api/week4/visuals/${discussionId}/interaction_graph`;

  // If we have a backend PNG, display it.
  const hasPng = data?.interaction_graph_url != null || !imgError;

  // Fallback: build a minimal SVG from edges + influence data from the analytics state.
  const influenceMetric = analyticsState.metrics.influence;
  const hasInfluence = influenceMetric.state === "ready";

  if (!hasPng || imgError) {
    // SVG fallback — draw agents as circles with directional edges.
    const influenceEntries = hasInfluence
      ? (influenceMetric.data as Array<{ agent_id: string; influence: number | null }>)
      : [];

    const influenceMap = new Map(influenceEntries.map((e) => [e.agent_id, e.influence ?? 0]));
    const agentIds = analyticsState.metrics.opinion_change.state === "ready"
      ? [...new Set((analyticsState.metrics.opinion_change.data as Array<{ agent_id: string }>).map((e) => e.agent_id))]
      : [];

    const n = agentIds.length;
    const cx = 200;
    const cy = 200;
    const radius = 130;

    const positions = agentIds.map((_, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
    });

    return (
      <div>
        <p className="mb-3 text-xs text-slate-400 dark:text-slate-500">
          Backend visual unavailable — showing client-side fallback from analytics data.
        </p>
        <div className="flex justify-center">
          <svg
            width="400"
            height="400"
            viewBox="0 0 400 400"
            aria-label="Agent interaction graph"
            role="img"
          >
            {/* Draw edges */}
            {agentIds.map((srcId, si) =>
              agentIds
                .filter((_, ti) => ti !== si)
                .map((tgtId, ti) => {
                  const src = positions[si];
                  const tgt = positions[agentIds.indexOf(tgtId)];
                  const inf = influenceMap.get(srcId) ?? 0;
                  return (
                    <line
                      key={`${srcId}-${tgtId}`}
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke="#cbd5e1"
                      strokeWidth={Math.max(1, (inf) * 3)}
                      opacity={0.5}
                    />
                  );
                }),
            )}

            {/* Draw nodes */}
            {agentIds.map((id, i) => {
              const pos = positions[i];
              const color = getAgentColor(id);
              const label = agentLabel(id).split(" ").slice(0, 2).join("\n");
              return (
                <g key={id}>
                  <circle cx={pos.x} cy={pos.y} r={28} fill={color} opacity={0.85} />
                  <text
                    x={pos.x}
                    y={pos.y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="white"
                    fontSize={9}
                    fontWeight="600"
                  >
                    {agentLabel(id).split(" ")[0]}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
        <p className="mt-2 text-center text-xs text-slate-400 dark:text-slate-500">
          Edge width proportional to influence magnitude
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="relative w-full overflow-hidden rounded-lg bg-slate-50 dark:bg-slate-800">
        {/* Next.js Image for the backend-generated PNG */}
        <div className="relative min-h-64">
          <img
            src={graphUrl}
            alt="Agent interaction graph showing edges weighted by influence"
            className="w-full object-contain"
            onError={() => setImgError(true)}
          />
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-slate-400 dark:text-slate-500">
        Edge width proportional to influence magnitude · Edge label = signed influence
      </p>
    </div>
  );
}
