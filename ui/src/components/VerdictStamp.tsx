import type { Verdict } from "../types";

export function VerdictStamp({ verdict }: { verdict: Verdict }) {
  const tag = verdict.tag.toLowerCase();
  return (
    <article className={`stamp stamp-${tag}${verdict.primary ? " stamp-primary" : ""}`}>
      <header>
        <span className="stamp-tag">{verdict.tag}</span>
        <span className="stamp-toxicity">{verdict.toxicity}</span>
      </header>
      <h3>{verdict.modern_name}</h3>
      <p>{verdict.summary}</p>
      <p className="caution">{verdict.caution}</p>
    </article>
  );
}
