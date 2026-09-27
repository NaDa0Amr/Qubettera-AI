"use client";

import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { clsx } from "clsx";
import { getAgentColor, getAgentBgColor, getAgentInitials } from "@/lib/palette";
import { truncate } from "@/lib/format";
import type { DiscussionMessage } from "@/types";

interface ChatMessageProps {
  message: DiscussionMessage;
  agentName: string;
}

export function ChatMessage({ message, agentName }: ChatMessageProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const color = getAgentColor(message.sender_id);
  const bgColor = getAgentBgColor(message.sender_id);
  const initials = getAgentInitials(agentName);
  const evidenceCount = message.evidence?.length ?? 0;

  return (
    <article
      data-testid={`message-${message.message_id}`}
      className="flex gap-3 group"
      aria-label={`Message from ${agentName}`}
    >
      {/* Avatar */}
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold mt-1"
        style={{ backgroundColor: bgColor, color }}
        aria-hidden="true"
      >
        {initials}
      </div>

      <div className="min-w-0 flex-1">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
            {agentName}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: bgColor, color }}
            aria-label={`Round ${message.round_number}, ${message.phase} phase`}
          >
            {message.phase === "initial" ? "Initial" : `R${message.round_number}`}
          </span>
        </div>

        {/* Message body — rendered as Markdown */}
        <div className="prose prose-sm prose-slate dark:prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Evidence / sources */}
        {evidenceCount > 0 && (
          <div className="mt-3">
            <button
              onClick={() => setSourcesOpen((o) => !o)}
              aria-expanded={sourcesOpen}
              aria-controls={`sources-${message.message_id}`}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
            >
              {sourcesOpen ? (
                <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              {evidenceCount} source{evidenceCount !== 1 ? "s" : ""}
            </button>

            {sourcesOpen && (
              <ul
                id={`sources-${message.message_id}`}
                className="mt-2 space-y-1"
                role="list"
                aria-label="Evidence sources"
              >
                {message.evidence.map((ev, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <span
                      className="shrink-0 mt-0.5 h-4 w-4 flex items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 font-mono text-[10px]"
                      aria-hidden="true"
                    >
                      {i + 1}
                    </span>
                    {ev.url ? (
                      <a
                        href={ev.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={clsx(
                          "flex items-center gap-1 text-indigo-600 hover:underline dark:text-indigo-400",
                        )}
                      >
                        {ev.title ? truncate(ev.title, 60) : truncate(ev.url, 60)}
                        <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                      </a>
                    ) : (
                      <span className="text-slate-500 dark:text-slate-400">
                        {ev.title ?? "Source"}
                      </span>
                    )}
                    <span className="ml-auto shrink-0 font-mono text-slate-400">
                      {ev.score?.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
