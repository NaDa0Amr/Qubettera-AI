export function Footer() {
  const techStack = [
    "Next.js 16",
    "FastAPI",
    "Supabase pgvector",
    "LangGraph",
    "ModernBERT",
  ];

  return (
    <footer className="border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
              Multi-Agent Opinion Simulation Platform
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Qubeterra AI NextGen Program — N-Labs AI Fellowship, Week 5
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {techStack.map((tech) => (
              <span
                key={tech}
                className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
        <p className="mt-4 text-xs text-slate-400 dark:text-slate-600">
          No authentication is implemented. This is a research prototype.
        </p>
      </div>
    </footer>
  );
}
