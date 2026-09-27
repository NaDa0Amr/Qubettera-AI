"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { DataTable } from "@/components/analytics/DataTable";
import { getAgentColor } from "@/lib/palette";
import type { SentimentEntry, SentimentPayload } from "@/types";

interface SentimentCardProps {
  data: unknown;
}

function sentimentColor(score: number): string {
  if (score > 0.2) return "#10b981"; // positive - emerald
  if (score < -0.2) return "#ef4444"; // negative - red
  return "#94a3b8"; // neutral - slate
}

function agentLabel(id: string) {
  return id.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export function SentimentCard({ data }: SentimentCardProps) {
  // The backend returns a SentimentPayload object, not a flat array.
  // Guard defensively: if somehow a flat array arrives, wrap it so the
  // component doesn't crash (makes it resilient to schema transitions).
  const payload = data as SentimentPayload | SentimentEntry[] | null | undefined;
  const entries: SentimentEntry[] =
    Array.isArray(payload)
      ? (payload as SentimentEntry[])
      : ((payload as SentimentPayload)?.messages ?? []);

  if (entries.length === 0) {
    return (
      <p className="text-sm text-slate-400 dark:text-slate-500 py-4 text-center">
        No sentiment data available.
      </p>
    );
  }

  // Stacked bar per round: positive/neutral/negative counts.
  const rounds = [...new Set(entries.map((e) => e.round))].sort((a, b) => a - b);
  const stackedData = rounds.map((round) => {
    const msgs = entries.filter((e) => e.round === round);
    return {
      round: `R${round}`,
      positive: msgs.filter((m) => m.label === "positive").length,
      neutral: msgs.filter((m) => m.label === "neutral").length,
      negative: msgs.filter((m) => m.label === "negative").length,
    };
  });

  // Heat strip data: one row per agent, grouped by round.
  const agentIds = [...new Set(entries.map((e) => e.agent_id))];

  const tableRows = entries.map((e) => ({
    message_id: e.message_id,
    agent: agentLabel(e.agent_id),
    agent_id: e.agent_id,
    round: e.round,
    sentiment: e.sentiment,
    label: e.label,
    confidence: e.confidence,
  }));

  return (
    <div className="space-y-6">
      {/* Stacked bar chart */}
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={stackedData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="round" tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis tick={{ fontSize: 11, fill: "#64748b" }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="positive" stackId="a" fill="#10b981" name="Positive" radius={[0, 0, 0, 0]} />
          <Bar dataKey="neutral" stackId="a" fill="#94a3b8" name="Neutral" />
          <Bar dataKey="negative" stackId="a" fill="#ef4444" name="Negative" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      {/* Heat strip */}
      <div className="space-y-2" aria-label="Sentiment heat strip">
        {agentIds.map((agentId) => {
          const agentEntries = entries
            .filter((e) => e.agent_id === agentId)
            .sort((a, b) => a.round - b.round);
          return (
            <div key={agentId} className="flex items-center gap-3">
              <span
                className="w-24 shrink-0 text-xs font-medium text-slate-600 dark:text-slate-400 truncate"
                style={{ color: getAgentColor(agentId) }}
              >
                {agentLabel(agentId)}
              </span>
              <div className="flex gap-1 flex-wrap" role="list" aria-label={`${agentLabel(agentId)} sentiment`}>
                {agentEntries.map((e) => (
                  <div
                    key={e.message_id}
                    role="listitem"
                    aria-label={`Round ${e.round}: ${e.label} (${e.sentiment.toFixed(2)})`}
                    title={`R${e.round}: ${e.label} (${e.sentiment.toFixed(2)})`}
                    className="h-5 w-5 rounded-sm"
                    style={{ backgroundColor: sentimentColor(e.sentiment) }}
                  />
                ))}
              </div>
            </div>
          );
        })}
        <div className="flex items-center gap-4 text-xs text-slate-400 dark:text-slate-500 mt-2">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-emerald-500" aria-hidden="true" />
            Positive
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-slate-400" aria-hidden="true" />
            Neutral
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-red-500" aria-hidden="true" />
            Negative
          </span>
        </div>
      </div>

      {/* Table */}
      <DataTable
        caption="Per-message sentiment scores"
        columns={[
          {
            key: "agent",
            header: "Agent",
            render: (v, row) => {
              const r = row as typeof tableRows[number];
              return (
                <span style={{ color: getAgentColor(r.agent_id) }} className="font-medium">
                  {String(v)}
                </span>
              );
            },
          },
          { key: "round", header: "Round" },
          {
            key: "sentiment",
            header: "Score",
            render: (v) => (
              <span className="font-mono">{(v as number).toFixed(2)}</span>
            ),
          },
          {
            key: "label",
            header: "Label",
            render: (v) => {
              const label = v as string;
              const colorMap: Record<string, string> = {
                positive: "text-emerald-600 dark:text-emerald-400",
                neutral: "text-slate-500",
                negative: "text-red-600 dark:text-red-400",
              };
              return (
                <span className={`capitalize ${colorMap[label] ?? ""}`}>
                  {label}
                </span>
              );
            },
          },
          {
            key: "confidence",
            header: "Confidence",
            render: (v) => (
              <span className="font-mono text-xs">{(v as number).toFixed(2)}</span>
            ),
          },
        ]}
        rows={tableRows as unknown as Record<string, unknown>[]}
        rowKey={(r, i) => `${String(r.message_id ?? i)}`}
      />
    </div>
  );
}
