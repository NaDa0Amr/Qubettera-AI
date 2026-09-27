"use client";

import { usePersonas } from "@/hooks/usePersonas";
import { PersonaCard } from "@/components/personas/PersonaCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";

export function PersonasTab() {
  const { personas, loading, error, refresh } = usePersonas();

  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="Loading personas">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-3">
            <div className="flex gap-3">
              <Skeleton height="h-10" width="w-10" rounded="rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton height="h-4" width="w-3/4" />
                <Skeleton height="h-3" width="w-1/2" />
              </div>
            </div>
            <Skeleton height="h-5" width="w-1/3" rounded="rounded-full" />
            <Skeleton height="h-3" width="w-full" />
            <Skeleton height="h-3" width="w-4/5" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load personas"
        message={error}
        onRetry={refresh}
      />
    );
  }

  if (personas.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-slate-400 dark:text-slate-500">
        No personas found.
      </p>
    );
  }

  return (
    <div>
      <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
        {personas.length} personas available. Click any card to view the full profile.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {personas.map((persona) => (
          <PersonaCard key={persona.id} persona={persona} />
        ))}
      </div>
    </div>
  );
}
