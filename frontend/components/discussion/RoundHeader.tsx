interface RoundHeaderProps {
  roundNumber: number;
  phase: "initial" | "discussion";
}

export function RoundHeader({ roundNumber, phase }: RoundHeaderProps) {
  const label = phase === "initial" ? "Initial Positions" : `Round ${roundNumber}`;

  return (
    <div
      className="sticky top-0 z-10 -mx-4 px-4 py-2 bg-slate-50/95 dark:bg-slate-900/95 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700"
      aria-label={`Section: ${label}`}
    >
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
          {label}
        </span>
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" aria-hidden="true" />
      </div>
    </div>
  );
}
