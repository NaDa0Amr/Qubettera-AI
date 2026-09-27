import { ExternalLink } from "lucide-react";
import { truncate } from "@/lib/format";
import type { EvidenceItem } from "@/types";

interface EvidencePanelProps {
  evidence: EvidenceItem[];
}

export function EvidencePanel({ evidence }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return (
      <p className="text-xs text-slate-400 dark:text-slate-500">
        No evidence for the latest turn.
      </p>
    );
  }

  return (
    <ul role="list" className="space-y-2" aria-label="Evidence from latest turn">
      {evidence.map((ev, i) => (
        <li key={i} className="text-xs">
          {ev.url ? (
            <a
              href={ev.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-1.5 text-indigo-600 hover:underline dark:text-indigo-400 group"
            >
              <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
              <span>{ev.title ? truncate(ev.title, 50) : truncate(ev.url, 50)}</span>
            </a>
          ) : (
            <span className="text-slate-500 dark:text-slate-400">
              {ev.title ?? "Source"}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
