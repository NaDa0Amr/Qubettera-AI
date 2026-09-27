"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
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

// Tunable timings — kept as module constants so they're easy to adjust
// without touching the render logic.
const STAGGER_STEP_MS = 80;   // delay between consecutive cards' fades
const FADE_IN_MS = 500;       // ready content fade-in duration
const CROSSFADE_MS = 250;     // skeleton overlay fade-out duration

export function MetricCard({
  title,
  description,
  status,
  onRetry,
  children,
  minHeight = "min-h-64",
  staggerIndex = 0,
}: MetricCardProps) {
  // readyOpacity: 0 → 1 when the metric content fades in.
  // crossfadeOpacity: 1 → 0 for the briefly-retained skeleton overlay.
  // Both are driven by state updates so the transition is smooth regardless
  // of which Tailwind animation plugins are installed.
  const [readyOpacity, setReadyOpacity] = useState(status.state === "ready" ? 1 : 0);
  const [crossfadeOpacity, setCrossfadeOpacity] = useState(0);
  const [showCrossfade, setShowCrossfade] = useState(false);
  const prevStateRef = useRef(status.state);

  useEffect(() => {
    const prev = prevStateRef.current;
    prevStateRef.current = status.state;

    // Detect the running/pending → ready transition. This is the only edge
    // that should trigger the fade + crossfade animation; subsequent renders
    // while already ready leave the card in its final visual state.
    if (prev !== "ready" && status.state === "ready") {
      const delayMs = staggerIndex * STAGGER_STEP_MS;

      // 1. After the stagger delay, mount the skeleton overlay at full
      //    opacity so it briefly appears on top of the ready content.
      const mountCrossfade = setTimeout(() => {
        setShowCrossfade(true);
        setCrossfadeOpacity(1);
      }, delayMs);

      // 2. On the next tick, drop its opacity to 0. The `transition` CSS
      //    property handles the smooth 250ms fade-out.
      const fadeCrossfade = setTimeout(() => {
        setCrossfadeOpacity(0);
      }, delayMs + 20);

      // 3. Unmount the overlay once the fade completes.
      const unmountCrossfade = setTimeout(() => {
        setShowCrossfade(false);
      }, delayMs + CROSSFADE_MS + 50);

      // 4. Fade the ready content in over FADE_IN_MS, starting at the
      //    same moment the crossfade begins.
      const fadeContent = setTimeout(() => {
        setReadyOpacity(1);
      }, delayMs);

      return () => {
        clearTimeout(mountCrossfade);
        clearTimeout(fadeCrossfade);
        clearTimeout(unmountCrossfade);
        clearTimeout(fadeContent);
      };
    }

    // If the state leaves ready (e.g. on retry), reset the animation state
    // so the next transition replays cleanly.
    if (status.state !== "ready") {
      setReadyOpacity(0);
      setCrossfadeOpacity(0);
      setShowCrossfade(false);
    }
  }, [status.state, staggerIndex]);

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

        {/* Ready content. Opacity is state-driven so the transition runs
            with a plain CSS `transition` — no Tailwind animation plugin
            required. */}
        {status.state === "ready" && (
          <div
            style={{
              opacity: readyOpacity,
              transition: `opacity ${FADE_IN_MS}ms ease-out`,
            }}
          >
            {children(status.data)}
          </div>
        )}

        {/* Crossfade overlay (change B). During the short window after the
            metric becomes ready, the previous skeleton is re-rendered on
            top of the new content and fades from full opacity to 0. The
            user perceives a smooth dissolve rather than an instant swap. */}
        {showCrossfade && (
          <div
            className="pointer-events-none absolute inset-0 px-5 py-5"
            style={{
              opacity: crossfadeOpacity,
              transition: `opacity ${CROSSFADE_MS}ms ease-out`,
            }}
            aria-hidden="true"
          >
            <RunningSkeleton />
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