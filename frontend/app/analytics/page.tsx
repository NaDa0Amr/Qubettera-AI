import Link from "next/link";

export const metadata = { title: "Analytics" };

export default function AnalyticsIndexPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-24 text-center">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-4">
        Analytics
      </h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
        No completed discussions with analytics yet. Run a discussion first, then return here.
      </p>
      <Link
        href="/discussions"
        className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
      >
        Start a Discussion
      </Link>
    </div>
  );
}

