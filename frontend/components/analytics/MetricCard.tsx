"use client";

import { ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { clsx } from "clsx";
import { Skeleton } from "@/components/ui/Skeleton";
import { InlineError } from "@/components/ui/ErrorState";
import { formatDuration } from "@/lib/format";
import type { MetricStatus } from "@/types";

interface MetricCardProps {
  title: string;
  description?: string;
  status: MetricStatus;
  onRetry?: () => void;
  children: (data: unknown) => ReactNode;
  minHeight?: string;
  /**
   * Position of this card in the dashboard (0-based). Used to stagger
   * the fade-in when multiple metrics complete in the same tick — e.g.
   * when the analytics result was already cached and every metric_completed
   * event arrives within a few milliseconds. The delay is capped implicitly:
   * with six metrics and an 80ms step, the last card starts 400ms after the
   * first, which is short enough to feel synchronous but long enough to
   * register as a wave rather than a pop.
   */
  staggerIndex?: number;
}

export function MetricCard({
  title,
  description,
  status,
  onRetry,
  children,
  minHeight = "min-h-64",
  staggerIndex = 0,
}: MetricCardProps) {
  return (
    <div
      className="rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 shadow-sm overflow-hidden"
      data-testid={`metric-card-${title.toLowerCase().replace(/\s+/g, "-")}`}
    >
      {/* Card header */}
      <div className="flex items-start justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
        <div>
          <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
            {title}
          </h3>
          {description && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {description}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {status.state === "ready" && (
            <span className="text-xs text-slate-400 font-mono">
              {formatDuration(status.durationMs)}
            </span>
          )}

          {/* Pulsing "Computing…" pill (change D). Previously this was a
              bare flex row; wrapping it in a rounded amber pill and adding
              `animate-pulse` to the container makes the running state
              visually louder and easier to spot at a glance. The spinner
              inside continues to provide the fine-grained motion. */}
          {status.state === "running" && (
            <span
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-full",
                "bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700",
                "animate-pulse",
                "dark:bg-amber-950 dark:text-amber-300",
              )}
            >
              <span
                className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                aria-hidden="true"
              />
              Computing…
            </span>
          )}

          {(status.state === "pending" || status.state === "failed") && onRetry && (
            <button
              onClick={onRetry}
              aria-label={`Retry ${title}`}
              className="rounded p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {/* Card body. `relative` is required so the crossfade overlay can
          position itself absolutely on top of the ready content. */}
      <div className={clsx("relative px-5 py-5", minHeight)}>
        {status.state === "pending" && <PendingSkeleton />}
        {status.state === "running" && <RunningSkeleton />}

        {status.state === "ready" && (
          <div className="metric-reveal" style={{ animationDelay: `${Math.min(staggerIndex, 5) * 80}ms` }}>
            {children(status.data)}
          </div>
        )}

        {status.state === "failed" && (
          <InlineError message={status.message} onRetry={onRetry} />
        )}
      </div>
    </div>
  );
}

function PendingSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading metric" aria-busy="true">
      <Skeleton height="h-48" className="w-full" />
      <Skeleton height="h-4" width="w-3/4" />
      <Skeleton height="h-4" width="w-1/2" />
    </div>
  );
}

function RunningSkeleton() {
  return (
    <div className="space-y-3" aria-label="Computing metric" aria-busy="true">
      <Skeleton height="h-48" className="w-full animate-pulse" />
      <Skeleton height="h-4" width="w-3/4" />
      <Skeleton height="h-4" width="w-1/2" />
    </div>
  );
}
