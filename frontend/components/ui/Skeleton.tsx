import { clsx } from "clsx";

interface SkeletonProps {
  className?: string;
  height?: string;
  width?: string;
  rounded?: string;
}

export function Skeleton({ className, height, width, rounded = "rounded-md" }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={clsx(
        "animate-pulse bg-slate-200 dark:bg-slate-700",
        rounded,
        height,
        width,
        className,
      )}
    />
  );
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-3 p-4" aria-label="Loading content" aria-busy="true">
      <Skeleton height="h-5" width="w-2/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height="h-4" width={i === lines - 1 ? "w-4/5" : "w-full"} />
      ))}
    </div>
  );
}
