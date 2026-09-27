"use client";

import { use } from "react";
import { useState } from "react";
import { useAnalyticsStream } from "@/hooks/useAnalyticsStream";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { StatusPill } from "@/components/layout/StatusPill";
import { DashboardTab } from "./_tabs/DashboardTab";
import { ReportTab } from "./_tabs/ReportTab";
import { VisualsTab } from "./_tabs/VisualsTab";
import { BarChart2, FileText, ImageIcon } from "lucide-react";
import { truncate } from "@/lib/format";

interface PageProps {
  params: Promise<{ discussionId: string }>;
}

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: <BarChart2 className="h-4 w-4" aria-hidden="true" /> },
  { id: "report", label: "Report", icon: <FileText className="h-4 w-4" aria-hidden="true" /> },
  { id: "visuals", label: "Visuals", icon: <ImageIcon className="h-4 w-4" aria-hidden="true" /> },
];

export default function AnalyticsPage({ params }: PageProps) {
  const { discussionId } = use(params);
  const { state, retryMetric } = useAnalyticsStream(discussionId);
  const [activeTab, setActiveTab] = useState("dashboard");

  const completedCount = state.progress.completed;
  const totalCount = state.progress.total;

  const headerStatus: "computing" | "ready" | "failed" | "idle" =
    state.streamStatus === "completed"
      ? "ready"
      : state.streamStatus === "failed"
        ? "failed"
        : state.streamStatus === "streaming"
          ? "computing"
          : "idle";

  const statusLabel =
    state.streamStatus === "streaming"
      ? `Computing ${completedCount}/${totalCount}`
      : state.streamStatus === "completed"
        ? "Ready"
        : state.streamStatus === "failed"
          ? "Failed"
          : "Starting…";

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Page header */}
      <div className="mb-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              Analytics
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="font-mono">{truncate(discussionId, 16)}…</span>
              <StatusPill status={headerStatus} label={statusLabel} />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <div className="mt-6">
        <TabPanel id="dashboard" activeTab={activeTab}>
          <DashboardTab
            discussionId={discussionId}
            state={state}
            retryMetric={retryMetric}
          />
        </TabPanel>
        <TabPanel id="report" activeTab={activeTab}>
          <ReportTab
            discussionId={discussionId}
            reportStatus={state.metrics.report}
          />
        </TabPanel>
        <TabPanel id="visuals" activeTab={activeTab}>
          <VisualsTab
            discussionId={discussionId}
            visualsStatus={state.metrics.visuals}
          />
        </TabPanel>
      </div>
    </div>
  );
}
