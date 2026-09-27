"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { DataTable } from "@/components/analytics/DataTable";
import { getAgentColor } from "@/lib/palette";
import { formatStance } from "@/lib/format";
import type { OpinionChangeEntry } from "@/types";

interface OpinionChangeCardProps {
  data: unknown;
}

export function OpinionChangeCard({ data }: OpinionChangeCardProps) {
  const entries = data as OpinionChangeEntry[];

  // Group by round for the line chart: [{ round, dr_aris: 0.62, prof_elena: -0.55, … }]
  const agentIds = [...new Set(entries.map((e) => e.agent_id))];
  const rounds = [...new Set(entries.map((e) => e.round))].sort((a, b) => a - b);

  const chartData = rounds.map((round) => {
    const row: Record<string, number | string> = { round: `R${round}` };
    for (const agentId of agentIds) {
      const entry = entries.find((e) => e.agent_id === agentId && e.round === round);
      if (entry?.stance != null) {
        row[agentId] = entry.stance;
      }
    }
    return row;
  });

  // Build human-readable names from IDs.
  function agentLabel(id: string) {
    return id.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  }

  // Table rows.
  const tableRows = entries.map((e) => ({
    agent: agentLabel(e.agent_id),
    agent_id: e.agent_id,
    round: e.round,
    stance: e.stance,
    change: e.change,
    reasoning: e.reasoning,
  }));

  return (
    <div className="space-y-6">
      {/* Line chart */}
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          {/* Reference bands */}
          <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="6 3" label={{ value: "Neutral", position: "insideLeft", fontSize: 10, fill: "#94a3b8" }} />
          <XAxis dataKey="round" tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickFormatter={(v: number) => formatStance(v)}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
            formatter={(value, name) => [
            typeof value === "number" ? formatStance(value) : String(value ?? "—"),
            typeof name === "string" ? agentLabel(name) : String(name),
          ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
            formatter={(value: string) => agentLabel(value)}
          />
          {agentIds.map((id) => (
            <Line
              key={id}
              type="monotone"
              dataKey={id}
              stroke={getAgentColor(id)}
              strokeWidth={2}
              dot={{ r: 4, fill: getAgentColor(id) }}
              activeDot={{ r: 6 }}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Data table */}
      <DataTable
        caption="Opinion change per agent per round"
        columns={[
          { key: "agent", header: "Agent" },
          { key: "round", header: "Round" },
          {
            key: "stance",
            header: "Stance",
            render: (v) =>
              v != null ? (
                <span className="font-mono">{formatStance(v as number)}</span>
              ) : (
                "—"
              ),
          },
          {
            key: "change",
            header: "Change",
            render: (v) => {
              if (v == null) return <span className="text-slate-400">—</span>;
              const n = v as number;
              return (
                <span className={`font-mono ${n > 0 ? "text-emerald-600" : n < 0 ? "text-red-600" : ""}`}>
                  {formatStance(n)}
                </span>
              );
            },
          },
          {
            key: "reasoning",
            header: "Reasoning",
            render: (v) => (
              <span className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                {String(v ?? "—")}
              </span>
            ),
          },
        ]}
        rows={tableRows as unknown as Record<string, unknown>[]}
        rowKey={(r, i) => `${String(r.agent_id)}-${String(r.round)}-${i}`}
      />
    </div>
  );
}
