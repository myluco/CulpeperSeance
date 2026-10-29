import type { Herb } from "../types";

export async function fetchHerbs(): Promise<Herb[]> {
  const response = await fetch("/api/herbs");
  if (!response.ok) throw new Error("The cabinet will not open.");
  const body = (await response.json()) as { herbs: Herb[] };
  return body.herbs;
}
