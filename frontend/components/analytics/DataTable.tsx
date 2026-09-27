"use client";

import { useState, ReactNode } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
import { clsx } from "clsx";

interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (value: unknown, row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  caption?: string;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  rowKey,
  caption,
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = sortKey
    ? [...rows].sort((a, b) => {
        const av = a[sortKey];
        const bv = b[sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sortDir === "asc" ? cmp : -cmp;
      })
    : rows;

  return (
    <div className={clsx("overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700", className)}>
      <table className="w-full text-sm" aria-label={caption}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                scope="col"
                className={clsx(
                  "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400",
                  "cursor-pointer select-none hover:text-slate-700 dark:hover:text-slate-200 transition-colors",
                  col.className,
                )}
                onClick={() => handleSort(String(col.key))}
                aria-sort={
                  sortKey === String(col.key)
                    ? sortDir === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                <div className="flex items-center gap-1">
                  {col.header}
                  {sortKey === String(col.key) ? (
                    sortDir === "asc" ? (
                      <ChevronUp className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="h-3 w-3" aria-hidden="true" />
                    )
                  ) : null}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {sorted.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
            >
              {columns.map((col) => {
                const value = row[String(col.key)];
                return (
                  <td
                    key={String(col.key)}
                    className={clsx(
                      "px-4 py-3 text-slate-700 dark:text-slate-300",
                      col.className,
                    )}
                  >
                    {col.render ? col.render(value, row) : String(value ?? "—")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && (
        <div className="px-4 py-8 text-center text-sm text-slate-400 dark:text-slate-500">
          No data available.
        </div>
      )}
    </div>
  );
}
