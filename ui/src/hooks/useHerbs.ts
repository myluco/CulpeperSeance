import { useEffect, useState } from "react";
import { fetchHerbs } from "../api/herbs";
import type { Herb } from "../types";

export function useHerbs() {
  const [herbs, setHerbs] = useState<Herb[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchHerbs()
      .then((rows) => {
        if (!controller.signal.aborted) setHerbs(rows);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "The cabinet will not open.");
      });
    return () => controller.abort();
  }, []);

  return { herbs, error, loading: herbs.length === 0 && error === null };
}
