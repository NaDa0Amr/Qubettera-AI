"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatDate } from "@/lib/format";
import type { DiscussionBrief } from "@/types";

interface BriefPanelProps {
  brief: DiscussionBrief;
  participantIds: string[];
  agentNames: Record<string, string>;
  numRounds: number;
  discussionId: string;
  createdAt: string;
}

export function BriefPanel({
  brief,
  participantIds,
  agentNames,
  numRounds,
  discussionId,
  createdAt,
}: BriefPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-slate-200 dark:border-slate-700">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="brief-panel-content"
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
      >
        <span>{open ? "Hide brief" : "Show brief"}</span>
        {open ? (
          <ChevronUp className="h-4 w-4" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div
          id="brief-panel-content"
          className="px-4 pb-4 space-y-3 text-sm text-slate-700 dark:text-slate-300"
        >
          {brief.objective && (
            <BriefField label="Objective" value={brief.objective} />
          )}
          {brief.constraints.length > 0 && (
            <BriefListField label="Constraints" items={brief.constraints} />
          )}
          {brief.topics.length > 0 && (
            <BriefListField label="Topics" items={brief.topics} />
          )}
          {brief.strict_notes.length > 0 && (
            <BriefListField label="Strict Notes" items={brief.strict_notes} />
          )}
          <BriefField
            label="Participants"
            value={participantIds.map((id) => agentNames[id] ?? id).join(", ")}
          />
          <BriefField label="Rounds" value={String(numRounds)} />
          <BriefField label="Discussion ID" value={discussionId} mono />
          <BriefField label="Started" value={formatDate(createdAt)} />
        </div>
      )}
    </div>
  );
}

function BriefField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        {label}
      </p>
      <p className={mono ? "font-mono text-xs mt-0.5" : "mt-0.5"}>{value}</p>
    </div>
  );
}

function BriefListField({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        {label}
      </p>
      <ul className="mt-1 list-disc list-inside space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-sm">{item}</li>
        ))}
      </ul>
    </div>
  );
}
