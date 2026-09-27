// Deterministic agent color palette.
// Colors are assigned by hashing the agent ID string modulo 8.
// The same agent always receives the same color across all pages and sessions.

const PALETTE: readonly string[] = [
  "#3b82f6", // blue-500
  "#ef4444", // red-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
];

// Background variants (lighter, for avatar fills)
const PALETTE_BG: readonly string[] = [
  "#dbeafe", // blue-100
  "#fee2e2", // red-100
  "#d1fae5", // emerald-100
  "#fef3c7", // amber-100
  "#ede9fe", // violet-100
  "#fce7f3", // pink-100
  "#ccfbf1", // teal-100
  "#ffedd5", // orange-100
];

function hashId(id: string): number {
  let sum = 0;
  for (let i = 0; i < id.length; i++) {
    sum += id.charCodeAt(i);
  }
  return sum % PALETTE.length;
}

export function getAgentColor(agentId: string): string {
  return PALETTE[hashId(agentId)];
}

export function getAgentBgColor(agentId: string): string {
  return PALETTE_BG[hashId(agentId)];
}

export function getAgentInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

export function allColors(): readonly string[] {
  return PALETTE;
}
