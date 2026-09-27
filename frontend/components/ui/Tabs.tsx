"use client";

import { ReactNode } from "react";
import { clsx } from "clsx";

interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, activeTab, onTabChange, className }: TabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Page tabs"
      className={clsx("flex border-b border-slate-200 dark:border-slate-700", className)}
    >
      {tabs.map((tab, index) => (
        <button
          type="button"
          key={tab.id}
          role="tab"
          id={`tab-${tab.id}`}
          aria-selected={activeTab === tab.id}
          tabIndex={activeTab === tab.id ? 0 : -1}
          aria-controls={`tabpanel-${tab.id}`}
          data-testid={`tab-${tab.id}`}
          onClick={() => onTabChange(tab.id)}
          onKeyDown={(event) => {
            let nextIndex: number;
            switch (event.key) {
              case "ArrowRight": nextIndex = (index + 1) % tabs.length; break;
              case "ArrowLeft": nextIndex = (index - 1 + tabs.length) % tabs.length; break;
              case "Home": nextIndex = 0; break;
              case "End": nextIndex = tabs.length - 1; break;
              default: return;
            }
            event.preventDefault();
            const nextTab = tabs[nextIndex];
            onTabChange(nextTab.id);
            document.getElementById(`tab-${nextTab.id}`)?.focus();
          }}
          className={clsx(
            "flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors duration-150 -mb-px",
            activeTab === tab.id
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 dark:text-slate-400 dark:hover:text-slate-200",
          )}
        >
          {tab.icon && <span aria-hidden="true">{tab.icon}</span>}
          {tab.label}
        </button>
      ))}
    </div>
  );
}

interface TabPanelProps {
  id: string;
  activeTab: string;
  children: ReactNode;
  className?: string;
}

export function TabPanel({ id, activeTab, children, className }: TabPanelProps) {
  if (activeTab !== id) return null;
  return (
    <div
      role="tabpanel"
      tabIndex={0}
      id={`tabpanel-${id}`}
      aria-labelledby={`tab-${id}`}
      data-testid={`tabpanel-${id}`}
      className={className}
    >
      {children}
    </div>
  );
}
