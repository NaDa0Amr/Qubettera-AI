"use client";

import { useResource } from "@/hooks/useResource";
import type { Persona } from "@/types";

async function parsePersonas(response: Response): Promise<Persona[]> {
  const data = await response.json();
  return data.personas;
}

export function usePersonas() {
  const { data, ...state } = useResource("/api/personas", parsePersonas);
  return { personas: data ?? [], ...state };
}
