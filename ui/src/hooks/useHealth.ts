import { useEffect, useState } from "react";
import { fetchHealth } from "../api/health";
import type { Health } from "../types";

export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth()
      .then((body) => {
        if (!controller.signal.aborted) setHealth(body);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "The circle did not answer.");
      });
    return () => controller.abort();
  }, []);

  return { health, error };
}
