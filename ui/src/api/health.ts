import type { Health } from "../types";

export async function fetchHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok && response.status !== 503) {
    throw new Error("The circle did not answer.");
  }
  return response.json() as Promise<Health>;
}
