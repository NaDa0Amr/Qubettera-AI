import { clsx } from "clsx";
import { getAgentColor, getAgentBgColor, getAgentInitials } from "@/lib/palette";
import type { ParticipantState } from "@/types";

interface ParticipantListProps {
  participants: Record<string, ParticipantState>;
  agentNames: Record<string, string>;
}

const STATUS_CONFIG = {
  idle: { label: "Idle", dot: "bg-slate-300 dark:bg-slate-600" },
  speaking: { label: "Speaking", dot: "bg-indigo-500 animate-pulse" },
  spoke: { label: "Spoke", dot: "bg-emerald-500" },
  errored: { label: "Error", dot: "bg-red-500" },
};

export function ParticipantList({ participants, agentNames }: ParticipantListProps) {
  const entries = Object.values(participants);

  if (entries.length === 0) {
    return (
      <p className="text-xs text-slate-400 dark:text-slate-500">
        Participants will appear when the discussion starts.
      </p>
    );
  }

  return (
    <ul role="list" className="space-y-2" aria-label="Participants">
      {entries.map((p) => {
        const name = agentNames[p.id] ?? p.id;
        const color = getAgentColor(p.id);
        const bgColor = getAgentBgColor(p.id);
        const initials = getAgentInitials(name);
        const statusCfg = STATUS_CONFIG[p.status];

        return (
          <li
            key={p.id}
            className="flex items-center gap-2.5"
            aria-label={`${name}: ${statusCfg.label}`}
          >
            <div
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
              style={{ backgroundColor: bgColor, color }}
              aria-hidden="true"
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                {name}
              </p>
            </div>
            <span
              className={clsx(
                "flex h-2 w-2 shrink-0 rounded-full",
                statusCfg.dot,
              )}
              aria-hidden="true"
            />
            <span className="sr-only">{statusCfg.label}</span>
          </li>
        );
      })}
    </ul>
  );
}
