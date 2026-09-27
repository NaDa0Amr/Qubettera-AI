"use client";

import { useState, useEffect } from "react";
import type { Persona } from "@/types";

interface UsePersonasResult {
  personas: Persona[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function usePersonas(): UsePersonasResult {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch("/api/personas")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<{ personas: Persona[] }>;
      })
      .then((data) => {
        if (!cancelled) {
          setPersonas(data.personas);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load personas.");
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [tick]);

  return {
    personas,
    loading,
    error,
    refresh: () => setTick((t) => t + 1),
  };
}
