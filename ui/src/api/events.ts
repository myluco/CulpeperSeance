import type { SeanceEvent, Turn } from "../types";

export function applyEvent(turn: Turn, event: SeanceEvent): Turn {
  switch (event.type) {
    case "status":
      return { ...turn, stage: event.stage };
    case "sources":
      return { ...turn, sources: event.sources };
    case "token":
      return { ...turn, tokens: [...turn.tokens, event.text], stage: "speaking" };
    case "verdict":
      return { ...turn, verdicts: event.verdicts };
    case "refusal":
      return { ...turn, refusal: { reason: event.reason, text: event.text }, pending: false };
    case "error":
      return { ...turn, error: event.message, pending: false };
    case "done":
      return { ...turn, pending: false, stage: null };
    default:
      return turn;
  }
}
