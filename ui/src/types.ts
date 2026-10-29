export type Source = {
  herb_id: string;
  herb: string;
  section: string;
  planet: string;
  aliases: string;
  text: string;
  relevance: number;
  named: boolean;
};

export type Verdict = {
  herb_id: string;
  primary: boolean;
  herb: string;
  modern_name: string;
  tag: string;
  toxicity: string;
  summary: string;
  caution: string;
};

export type Herb = {
  id: string;
  herb: string;
  modern_name: string;
  tag: string;
  toxicity: string;
  summary: string;
  caution: string;
};

export type Health = {
  ok: boolean;
  ollama: boolean;
  store: boolean;
  chat_model: string;
};

export type SeanceEvent =
  | { type: "status"; stage: string; relevant?: boolean; by?: string; best?: number; query?: string }
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "verdict"; verdicts: Verdict[] }
  | { type: "refusal"; reason: string; text: string }
  | { type: "error"; message: string }
  | { type: "done" };

export type Turn = {
  id: string;
  question: string;
  tokens: string[];
  sources: Source[];
  verdicts: Verdict[];
  refusal: { reason: string; text: string } | null;
  error: string | null;
  stage: string | null;
  pending: boolean;
};
