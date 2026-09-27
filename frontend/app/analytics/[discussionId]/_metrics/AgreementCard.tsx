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
import { formatPercent } from "@/lib/format";
import type { AgreementEntry } from "@/types";

interface AgreementCardProps {
  data: unknown;
}

// Interpolate red (#ef4444) to green (#10b981) based on value in [0, 1].
function agreementColor(value: number): string {
  const r = Math.round(239 + (16 - 239) * value);
  const g = Math.round(68 + (185 - 68) * value);
  const b = Math.round(68 + (129 - 68) * value);
  return `rgb(${r},${g},${b})`;
}

export function AgreementCard({ data }: AgreementCardProps) {
  const entries = data as AgreementEntry[];

  const chartData = entries
    .sort((a, b) => a.round - b.round)
    .map((e) => ({ round: `R${e.round}`, agreement: e.agreement }));

  const tableRows = entries.map((e) => ({
    round: e.round,
    agreement: e.agreement,
    n_agents: e.n_agents,
  }));

  return (
    <div className="space-y-6">
      {/* Bar chart */}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="round" tick={{ fontSize: 11, fill: "#64748b" }} />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: "#64748b" }}
            tickFormatter={(v: number) => formatPercent(v)}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
            formatter={(v) => [
            typeof v === "number" ? formatPercent(v) : String(v ?? ""),
            "Agreement",
          ]}
          />
          <Bar dataKey="agreement" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={agreementColor(entry.agreement)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Inline key */}
      <div className="flex items-center gap-6 text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-sm bg-red-400" aria-hidden="true" />
          0 = perfect disagreement
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-sm bg-emerald-500" aria-hidden="true" />
          1 = unanimous
        </span>
      </div>

      {/* Table */}
      <DataTable
        caption="Agreement per round"
        columns={[
          { key: "round", header: "Round" },
          {
            key: "agreement",
            header: "Agreement",
            render: (v) => (
              <span className="font-mono">{formatPercent(v as number)}</span>
            ),
          },
          { key: "n_agents", header: "Agents" },
        ]}
        rows={tableRows as unknown as Record<string, unknown>[]}
        rowKey={(_, i) => `agreement-${i}`}
      />
    </div>
  );
}
