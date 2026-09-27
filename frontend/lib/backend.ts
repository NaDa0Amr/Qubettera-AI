import "server-only";

import { serverEnv } from "@/lib/env";
import mockPersonas from "@/lib/mocks/personas.json";
import type { DiscussionSummary, Persona } from "@/types";

async function fetchCollection<T>(path: string, key: string): Promise<T[]> {
  const response = await fetch(`${serverEnv.fastapiUrl}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
  const data = await response.json();
  const items = Array.isArray(data) ? data : data?.[key];
  if (!Array.isArray(items)) throw new Error(`Invalid ${key} response`);
  return items;
}

export async function getPersonas(): Promise<Persona[]> {
  if (serverEnv.mockBackend) return mockPersonas.personas as Persona[];
  return fetchCollection<Persona>("/personas", "personas");
}

export async function getDiscussions(): Promise<DiscussionSummary[]> {
  if (serverEnv.mockBackend) {
    return [{
      discussion_id: "mock-discussion-001",
      topic: "MoE vs Dense Layers for a 1B Parameter Transformer",
      created_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      num_rounds: 3,
      num_agents: 4,
      status: "completed",
      has_analytics: true,
    }];
  }
  return fetchCollection<DiscussionSummary>("/discussions", "discussions");
}
