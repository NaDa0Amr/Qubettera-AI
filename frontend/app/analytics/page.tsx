import Link from "next/link";
import { redirect } from "next/navigation";
import { getDiscussions } from "@/lib/backend";

export const metadata = { title: "Analytics" };
export const dynamic = "force-dynamic";

export default async function AnalyticsIndexPage() {
  let latestId: string | undefined;
  let unavailable = false;
  try {
    const discussions = await getDiscussions();
    latestId = discussions
      .filter((discussion) => discussion.status === "completed" && discussion.has_analytics)
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0]?.discussion_id;
  } catch {
    unavailable = true;
  }
  if (latestId) redirect(`/analytics/${encodeURIComponent(latestId)}`);

  return (
    <div className="mx-auto max-w-2xl px-4 py-24 text-center">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-4">
        Analytics
      </h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
        {unavailable
          ? "Discussion history is temporarily unavailable. Check the backend connection and try again."
          : "No saved analytics yet. Open a completed live discussion from history to run its analysis."}
      </p>
      <Link
        href="/discussions"
        className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
      >
        Open Discussions
      </Link>
    </div>
  );
}

