import { getAgentColor, getAgentBgColor, getAgentInitials } from "@/lib/palette";

interface StreamingMessageProps {
  agentId: string;
  agentName: string;
  text: string;
}

export function StreamingMessage({ agentId, agentName, text }: StreamingMessageProps) {
  const color = getAgentColor(agentId);
  const bgColor = getAgentBgColor(agentId);
  const initials = getAgentInitials(agentName);

  return (
    <article
      className="flex gap-3"
      aria-label={`${agentName} is speaking`}
      aria-live="polite"
      aria-atomic="false"
    >
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold mt-1"
        style={{ backgroundColor: bgColor, color }}
        aria-hidden="true"
      >
        {initials}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
            {agentName}
          </span>
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium animate-pulse"
            style={{ backgroundColor: bgColor, color }}
          >
            Speaking
          </span>
        </div>

        {/* Plain text during streaming — avoids partial Markdown parse flicker */}
        <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed">
          {text}
          <span className="inline-block w-0.5 h-4 bg-slate-500 ml-0.5 animate-pulse align-middle" aria-hidden="true" />
        </p>
      </div>
    </article>
  );
}
