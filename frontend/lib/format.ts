// Date, number, and stance formatters used across the UI.

/**
 * Format an ISO timestamp as a human-readable date + time string.
 * Example: "Sep 21, 2026, 20:30"
 */
export function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/**
 * Format an ISO timestamp as a relative string.
 * Example: "2 min ago", "1 hr ago", "3 days ago"
 */
export function formatRelativeTime(iso: string): string {
  try {
    const delta = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(delta / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} hr ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days !== 1 ? "s" : ""} ago`;
  } catch {
    return iso;
  }
}

/**
 * Format a stance score in [−1, +1] with sign and 2 decimal places.
 * Example: +0.62, −0.31, 0.00
 */
export function formatStance(n: number): string {
  if (n === null || n === undefined) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}`;
}

/**
 * Format a value in [0, 1] as a percentage.
 * Example: 0.41 → "41%"
 */
export function formatPercent(n: number): string {
  return `${Math.round(n * 100)}%`;
}

/**
 * Format a duration in milliseconds as a human-readable string.
 * Example: 45210 → "45.2s"
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Truncate a string to maxLen characters, appending ellipsis if needed.
 */
export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 1) + "…";
}
