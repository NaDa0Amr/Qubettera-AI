import { publicEnv } from "@/lib/env";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <p className="font-semibold text-slate-900 dark:text-slate-100">{publicEnv.appName}</p>
        <p className="text-slate-500 dark:text-slate-400">Research, discussion, and evidence in one workspace.</p>
      </div>
    </footer>
  );
}
