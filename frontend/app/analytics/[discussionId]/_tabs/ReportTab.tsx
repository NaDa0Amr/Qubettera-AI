/* eslint-disable @next/next/no-img-element -- Report images have runtime dimensions and are served by the backend proxy. */
"use client";

import { useResource } from "@/hooks/useResource";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { InlineError } from "@/components/ui/ErrorState";
import type { MetricStatus } from "@/types";

interface ReportTabProps {
  discussionId: string;
  reportStatus: MetricStatus;
}

async function parseReport(response: Response): Promise<string> {
  return response.text();
}

export function ReportTab({ discussionId, reportStatus }: ReportTabProps) {
  const isReady = reportStatus.state === "ready";
  const { data: markdown, loading, error } = useResource(
    isReady ? `/api/week4/report/${encodeURIComponent(discussionId)}` : null,
    parseReport,
  );

  function downloadReport() {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `discussion-${discussionId}-report.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-slate-400" aria-hidden="true" />
          <h2 className="font-semibold text-sm text-slate-900 dark:text-slate-100">
            Analytics Report
          </h2>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={downloadReport}
          disabled={!markdown}
          id="download-report-btn"
        >
          <Download className="h-4 w-4" aria-hidden="true" />
          Download .md
        </Button>
      </div>

      {/* Body */}
      <div className="px-6 py-6">
        {reportStatus.state === "pending" && (
          <div className="space-y-3">
            <Skeleton height="h-6" width="w-1/3" />
            <Skeleton height="h-4" width="w-full" />
            <Skeleton height="h-4" width="w-full" />
            <Skeleton height="h-4" width="w-3/4" />
          </div>
        )}

        {reportStatus.state === "running" && (
          <div className="flex items-center gap-3 py-8 text-sm text-slate-500 dark:text-slate-400">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
            Generating report…
          </div>
        )}

        {reportStatus.state === "failed" && (
          <InlineError
            message={`Report generation failed: ${reportStatus.message}`}
          />
        )}

        {isReady && loading && (
          <div className="space-y-3">
            <Skeleton height="h-6" width="w-1/2" />
            <Skeleton height="h-4" width="w-full" />
            <Skeleton height="h-4" width="w-full" />
          </div>
        )}

        {isReady && error && (
          <InlineError message={error} />
        )}

        {isReady && markdown && !loading && (
          <article
            className="prose prose-sm dark:prose-invert max-w-none"
            aria-label="Analytics report"
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                img: ({ src, alt }) => {
                  // ReactMarkdown types `src` as `string | Blob | undefined`
                  // (it mirrors the DOM HTMLImageElement.src type in some
                  // versions). Neither `.startsWith` nor `.split` exists on
                  // Blob, so narrow to string first. In practice the value is
                  // always a string when parsed from Markdown, but the type
                  // guard is what makes TypeScript accept the string methods
                  // below.
                  if (typeof src !== "string" || !src) return null;

                  // New format emitted by the backend: /week4/visuals/{id}/{name}.
                  // Prefix with /api so the request goes through the Next.js proxy
                  // (app/api/week4/visuals/[id]/[name]/route.ts), which forwards it
                  // to the FastAPI backend.
                  if (src.startsWith("/week4/")) {
                    return (
                      <img
                        src={`/api${src}`}
                        alt={alt ?? ""}
                        className="my-4 w-full rounded-lg border border-slate-200 dark:border-slate-700"
                      />
                    );
                  }

                  // Legacy format from older reports: ../visuals/{name}_{id}.png.
                  // The relative path resolves against the browser's current URL, not
                  // the backend filesystem, so it 404s. Rewrite it to the proxied URL.
                  // This handles report files that were generated before the backend
                  // fix and never regenerated.
                  const filename = src.split("/").pop() ?? "";
                  const suffix = `_${discussionId}.png`;
                  if (
                    (src.startsWith("../visuals/") || src.startsWith("./visuals/")) &&
                    filename.endsWith(suffix)
                  ) {
                    const name = filename.slice(0, -suffix.length);
                    return (
                      <img
                        src={`/api/week4/visuals/${discussionId}/${name}`}
                        alt={alt ?? ""}
                        className="my-4 w-full rounded-lg border border-slate-200 dark:border-slate-700"
                      />
                    );
                  }

                  // Any other src (rare, or user-authored markdown) is rendered as-is.
                  return <img src={src} alt={alt ?? ""} className="my-4 w-full" />;
                },
              }}
            >
              {markdown}
            </ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}