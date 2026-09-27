"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { MessageSquare, Clock, Users } from "lucide-react";
import { RunTab } from "./_tabs/RunTab";
import { HistoryTab } from "./_tabs/HistoryTab";
import { PersonasTab } from "./_tabs/PersonasTab";

type TabId = "run" | "history" | "personas";

const TABS = [
  { id: "run", label: "Run", icon: <MessageSquare className="h-4 w-4" aria-hidden="true" /> },
  { id: "history", label: "History", icon: <Clock className="h-4 w-4" aria-hidden="true" /> },
  { id: "personas", label: "Personas", icon: <Users className="h-4 w-4" aria-hidden="true" /> },
];

// Inner component that reads searchParams — must be wrapped in Suspense.
function DiscussionsContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab") as TabId | null;
  const router = useRouter();
  const activeTab = tabParam && ["run", "history", "personas"].includes(tabParam) ? tabParam : "run";

  return (
    <>
      <Tabs
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={(id) => {
          const nextParams = new URLSearchParams(searchParams.toString());
          nextParams.set("tab", id);
          router.replace(`/discussions?${nextParams}`, { scroll: false });
        }}
      />
      <div className="mt-6">
        <TabPanel id="run" activeTab={activeTab}>
          <RunTab />
        </TabPanel>
        <TabPanel id="history" activeTab={activeTab}>
          <HistoryTab />
        </TabPanel>
        <TabPanel id="personas" activeTab={activeTab}>
          <PersonasTab />
        </TabPanel>
      </div>
    </>
  );
}

export default function DiscussionsPage() {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Discussions</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Run a new multi-agent debate, browse past discussions, or explore agent personas.
        </p>
      </div>

      {/*
        useSearchParams() requires Suspense boundary in the App Router.
        Fallback shows the tab bar skeleton so the layout doesn't shift.
      */}
      <Suspense
        fallback={
          <div className="flex border-b border-slate-200 dark:border-slate-700 mb-6">
            {TABS.map((tab) => (
              <div
                key={tab.id}
                className="px-5 py-3 text-sm font-medium text-slate-400 border-b-2 border-transparent"
              >
                {tab.label}
              </div>
            ))}
          </div>
        }
      >
        <DiscussionsContent />
      </Suspense>
    </div>
  );
}
