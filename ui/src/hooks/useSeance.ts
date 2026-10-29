import { useState } from "react";
import { ask } from "../api/ask";
import { applyEvent } from "../api/events";
import type { Turn } from "../types";

function blankTurn(question: string): Turn {
  return {
    id: crypto.randomUUID(),
    question,
    tokens: [],
    sources: [],
    verdicts: [],
    refusal: null,
    error: null,
    stage: "searching",
    pending: true,
  };
}

export function useSeance() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);

  async function submit(question: string) {
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    const turn = blankTurn(trimmed);
    setTurns((prev) => [...prev, turn]);
    setAsking(true);
    const controller = new AbortController();
    try {
      for await (const event of ask(trimmed, controller.signal)) {
        setTurns((prev) => prev.map((item) => (item.id === turn.id ? applyEvent(item, event) : item)));
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const message = err instanceof Error ? err.message : "The séance was disturbed.";
      setTurns((prev) => prev.map((item) => (item.id === turn.id ? { ...item, error: message, pending: false } : item)));
    } finally {
      setAsking(false);
      setTurns((prev) => prev.map((item) => (item.id === turn.id && item.pending ? { ...item, pending: false } : item)));
    }
  }

  return { turns, asking, submit };
}
