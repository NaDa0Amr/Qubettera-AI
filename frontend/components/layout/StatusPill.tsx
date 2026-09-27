import { clsx } from "clsx";

type Status =
  | "idle"
  | "streaming"
  | "done"
  | "error"
  | "computing"
  | "ready"
  | "failed"
  | "complete"
  | "degraded";

interface StatusPillProps {
  status: Status;
  label?: string;
  className?: string;
}

const CONFIG: Record<Status, { dot: string; bg: string; text: string; defaultLabel: string }> = {
  idle: {
    dot: "bg-slate-400",
    bg: "bg-slate-100 dark:bg-slate-800",
    text: "text-slate-600 dark:text-slate-300",
    defaultLabel: "Idle",
  },
  streaming: {
    dot: "bg-indigo-500 animate-pulse",
    bg: "bg-indigo-50 dark:bg-indigo-950",
    text: "text-indigo-700 dark:text-indigo-300",
    defaultLabel: "Streaming",
  },
  done: {
    dot: "bg-emerald-500",
    bg: "bg-emerald-50 dark:bg-emerald-950",
    text: "text-emerald-700 dark:text-emerald-300",
    defaultLabel: "Complete",
  },
  complete: {
    dot: "bg-emerald-500",
    bg: "bg-emerald-50 dark:bg-emerald-950",
    text: "text-emerald-700 dark:text-emerald-300",
    defaultLabel: "Complete",
  },
  ready: {
    dot: "bg-emerald-500",
    bg: "bg-emerald-50 dark:bg-emerald-950",
    text: "text-emerald-700 dark:text-emerald-300",
    defaultLabel: "Ready",
  },
  error: {
    dot: "bg-red-500",
    bg: "bg-red-50 dark:bg-red-950",
    text: "text-red-700 dark:text-red-300",
    defaultLabel: "Error",
  },
  failed: {
    dot: "bg-red-500",
    bg: "bg-red-50 dark:bg-red-950",
    text: "text-red-700 dark:text-red-300",
    defaultLabel: "Failed",
  },
  computing: {
    dot: "bg-amber-500 animate-pulse",
    bg: "bg-amber-50 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-300",
    defaultLabel: "Computing",
  },
  degraded: {
    dot: "bg-amber-500",
    bg: "bg-amber-50 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-300",
    defaultLabel: "Degraded",
  },
};

export function StatusPill({ status, label, className }: StatusPillProps) {
  const { dot, bg, text, defaultLabel } = CONFIG[status];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        bg,
        text,
        className,
      )}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", dot)} aria-hidden="true" />
      {label ?? defaultLabel}
    </span>
  );
}
