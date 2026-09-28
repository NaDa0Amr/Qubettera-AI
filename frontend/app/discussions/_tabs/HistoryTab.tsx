"use client";

import Link from "next/link";
import { useAutoRefreshDiscussionHistory } from "@/hooks/useDiscussionHistory";
import { useDiscussion } from "@/contexts/DiscussionContext";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { StatusPill } from "@/components/layout/StatusPill";
import { formatRelativeTime, truncate } from "@/lib/format";
import { RefreshCw, ExternalLink } from "lucide-react";

export function HistoryTab() {
  const { state } = useDiscussion();
  const { discussions, loading, error, refresh } = useAutoRefreshDiscussionHistory(state.status);

  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading discussion history">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-slate-200 dark:border-slate-700 p-4">
            <Skeleton height="h-4" width="w-2/3" className="mb-2" />
            <Skeleton height="h-3" width="w-1/3" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load discussion history"
        message={error}
        onRetry={refresh}
      />
    );
  }

  if (discussions.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No discussions yet. Run one from the Run tab.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {discussions.length} discussion{discussions.length !== 1 ? "s" : ""}
        </p>
        <button
          onClick={refresh}
          aria-label="Refresh discussion history"
          className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Refresh
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
        <table className="w-full text-sm" aria-label="Past discussions">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Topic
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 hidden sm:table-cell">
                Agents
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 hidden md:table-cell">
                Rounds
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 hidden md:table-cell">
                Created
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Status
              </th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {discussions.map((d) => (
              <tr
                key={d.discussion_id}
                className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
              >
                <td className="px-4 py-4 text-slate-800 dark:text-slate-200 max-w-xs">
                  <p className="font-medium">{truncate(d.topic, 60) || "Untitled discussion"}</p>
                  <p className="font-mono text-xs text-slate-400 mt-0.5">
                    {d.discussion_id.slice(0, 8)}…
                  </p>
                </td>
                <td className="px-4 py-4 text-slate-600 dark:text-slate-400 hidden sm:table-cell">
                  {d.num_agents ?? "—"}
                </td>
                <td className="px-4 py-4 text-slate-600 dark:text-slate-400 hidden md:table-cell">
                  {d.num_rounds ?? "—"}
                </td>
                <td className="px-4 py-4 text-slate-500 dark:text-slate-400 hidden md:table-cell whitespace-nowrap">
                  {formatRelativeTime(d.created_at)}
                </td>
                <td className="px-4 py-4">
                  <StatusPill
                    status={
                      d.status === "completed"
                        ? "done"
                        : d.status === "failed"
                          ? "failed"
                          : "streaming"
                    }
                    label={d.status}
                  />
                </td>
                <td className="px-4 py-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Link
                      href={`/discussions/${d.discussion_id}`}
                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      Open
                    </Link>
                    {d.has_analytics && (
                      <Link
                        href={`/analytics/${d.discussion_id}`}
                        className="inline-flex items-center gap-1 rounded-md bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 px-3 py-1.5 text-xs font-medium text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900 transition-colors"
                      >
                        Analytics
                      </Link>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
