"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { DataTable } from "@/components/analytics/DataTable";
import { getAgentColor } from "@/lib/palette";
import { AlertTriangle } from "lucide-react";
import type { InfluenceEntry } from "@/types";

interface InfluenceCardProps {
  data: unknown;
}

export function InfluenceCard({ data }: InfluenceCardProps) {
  const entries = (data as InfluenceEntry[])
    .slice()
    .sort((a, b) => Math.abs(b.influence ?? 0) - Math.abs(a.influence ?? 0));

  function agentLabel(id: string) {
    return id.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  }

  const chartData = entries.map((e) => ({
    agent: agentLabel(e.agent_id),
    agent_id: e.agent_id,
    influence: e.influence ?? 0,
    isNull: e.influence == null,
    note: e.note,
  }));

  const tableRows = entries.map((e) => ({
    agent: agentLabel(e.agent_id),
    agent_id: e.agent_id,
    influence: e.influence,
    condition_number: e.condition_number,
    note: e.note,
  }));

  return (
    <div className="space-y-6">
      {/* Horizontal bar chart */}
      <ResponsiveContainer width="100%" height={Math.max(180, entries.length * 52)}>
        <BarChart
          layout="vertical"
          data={chartData}
          margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <YAxis
            type="category"
            dataKey="agent"
            width={110}
            tick={{ fontSize: 11, fill: "#64748b" }}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
          formatter={(v, _name, props) => {
              const item = (props as { payload?: { note?: string; isNull?: boolean } }).payload;
              if (item?.isNull) return ["Unavailable", "Influence"];
              return [typeof v === "number" ? v.toFixed(3) : String(v ?? ""), "Influence"];
            }}
          />
          <Bar dataKey="influence" radius={[0, 4, 4, 0]}>
            {chartData.map((entry) => (
              <Cell
                key={entry.agent_id}
                fill={entry.isNull ? "#e2e8f0" : getAgentColor(entry.agent_id)}
                opacity={entry.isNull ? 0.6 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Table */}
      <DataTable
        caption="Influence per agent"
        columns={[
          { key: "agent", header: "Agent" },
          {
            key: "influence",
            header: "Influence",
            render: (v) => {
              if (v == null) {
                return (
                  <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
                    N/A
                  </span>
                );
              }
              return <span className="font-mono">{(v as number).toFixed(3)}</span>;
            },
          },
          {
            key: "condition_number",
            header: "Condition #",
            render: (v) => (
              <span className="font-mono text-xs">
                {v != null ? (v as number).toFixed(1) : "—"}
              </span>
            ),
          },
          {
            key: "note",
            header: "Note",
            render: (_value, row) => {
              const r = row as typeof tableRows[number];
              if (!r.note) return <span className="text-slate-300">—</span>;
              return (
                <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden="true" />
                  {r.note}
                </span>
              );
            },
          },
        ]}
        rows={tableRows as unknown as Record<string, unknown>[]}
        rowKey={(r) => String(r.agent_id)}
      />
    </div>
  );
}
