import type { Health } from "../types";

const STAGES: Record<string, string> = {
  searching: "Turning the pages of the herbal",
  graded: "Judging whether the page answers",
  rephrasing: "Seeking plainer words",
  rephrased: "Asking the book again",
  speaking: "The spirit draws breath",
};

export function summoningLabel(stage: string | null, health: Health | null): string {
  if (health && !health.ollama) return "Waiting for Ollama to wake";
  if (stage && STAGES[stage]) return STAGES[stage];
  return "Summoning";
}

export function Summoning({ stage, health }: { stage: string | null; health: Health | null }) {
  return (
    <p className="summoning" role="status">
      <span className="flame" aria-hidden="true" />
      {summoningLabel(stage, health)}
    </p>
  );
}
