"use client";

import { useState } from "react";
import { ImageOff, TrendingUp, Network, ExternalLink } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { InlineError } from "@/components/ui/ErrorState";
import type { MetricStatus } from "@/types";

interface VisualsTabProps {
  discussionId: string;
  /** The unified "visuals" metric status from the analytics stream. */
  visualsStatus: MetricStatus;
}

interface VisualImageProps {
  src: string;
  alt: string;
  label: string;
  icon: React.ReactNode;
}

/**
 * Renders a single backend-generated PNG with graceful fallback.
 * Falls back to an error state with a note when the image 404s.
 */
function VisualImage({ src, alt, label, icon }: VisualImageProps) {
  const [status, setStatus] = useState<"loading" | "loaded" | "error">("loading");

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
      {/* Card header */}
      <div className="flex items-center gap-2.5 border-b border-slate-100 px-5 py-3.5 dark:border-slate-800">
        <span className="text-slate-400 dark:text-slate-500">{icon}</span>
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{label}</h3>
        <a
          href={src}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors"
          aria-label={`Download ${label}`}
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          Open full size
        </a>
      </div>

      {/* Image container */}
      <div className="relative min-h-80 bg-slate-50 dark:bg-slate-800/50">
        {/* Skeleton while loading */}
        {status === "loading" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="space-y-3 w-2/3">
              <Skeleton height="h-64" width="w-full" />
            </div>
          </div>
        )}

        {/* Error state */}
        {status === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-400 dark:text-slate-500">
            <ImageOff className="h-10 w-10 opacity-40" aria-hidden="true" />
            <p className="text-sm text-center px-6">
              Image not generated yet — run analytics to produce this visual.
            </p>
          </div>
        )}

        {/* The actual image */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          className={[
            "w-full object-contain transition-opacity duration-300",
            status === "loaded" ? "opacity-100" : "opacity-0",
          ].join(" ")}
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("error")}
        />
      </div>

      {/* Caption */}
      {status === "loaded" && (
        <p className="px-5 py-3 text-xs text-slate-400 dark:text-slate-500 border-t border-slate-100 dark:border-slate-800">
          {alt}
        </p>
      )}
    </div>
  );
}

export function VisualsTab({ discussionId, visualsStatus }: VisualsTabProps) {
  const opinionTrajectoryUrl = `/api/week4/visuals/${discussionId}/opinion_trajectory`;
  const interactionGraphUrl = `/api/week4/visuals/${discussionId}/interaction_graph`;

  // Still waiting for analytics to finish
  if (visualsStatus.state === "pending") {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="border-b border-slate-100 px-5 py-3.5 dark:border-slate-800">
              <Skeleton height="h-5" width="w-40" />
            </div>
            <div className="min-h-80 p-5">
              <Skeleton height="h-64" width="w-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Analytics engine running
  if (visualsStatus.state === "running") {
    return (
      <div className="flex items-center justify-center gap-3 py-24 text-sm text-slate-500 dark:text-slate-400">
        <span
          className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
        Generating visual outputs…
      </div>
    );
  }

  // Engine reported failure
  if (visualsStatus.state === "failed") {
    return (
      <InlineError
        message={`Visual generation failed: ${visualsStatus.message}`}
      />
    );
  }

  // Ready — show both images side by side
  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Backend-generated visualisations for discussion{" "}
        <code className="font-mono text-xs">{discussionId}</code>. Images are
        served directly from the FastAPI backend.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <VisualImage
          src={opinionTrajectoryUrl}
          alt="Opinion trajectory — agent stance values across discussion rounds"
          label="Opinion Trajectory"
          icon={<TrendingUp className="h-4.5 w-4.5" aria-hidden="true" />}
        />

        <VisualImage
          src={interactionGraphUrl}
          alt="Agent interaction graph — edges weighted by influence magnitude"
          label="Interaction Graph"
          icon={<Network className="h-4.5 w-4.5" aria-hidden="true" />}
        />
      </div>

      <p className="text-xs text-slate-400 dark:text-slate-500">
        If either image shows an error, trigger analytics via{" "}
        <strong>Dashboard → Refresh</strong> to regenerate the visual outputs.
      </p>
    </div>
  );
}
