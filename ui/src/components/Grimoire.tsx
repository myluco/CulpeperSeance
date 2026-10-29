import type { Source } from "../types";

export function Grimoire({ sources }: { sources: Source[] }) {
  return (
    <aside className="grimoire">
      <header>
        <h2>Grimoire</h2>
        <p>The pages the spirit was given. The answer may not leave them.</p>
      </header>
      {sources.length === 0 ? (
        <p className="empty">The book is shut.</p>
      ) : (
        <ol>
          {sources.map((source, index) => (
            <li key={`${source.herb_id}-${source.section}-${index}`}>
              <header>
                <h3>{source.herb}</h3>
                <span>{source.section}</span>
                {source.planet ? <span>of {source.planet}</span> : null}
                {source.named ? <span className="named">named</span> : null}
                <span className="score">{source.relevance.toFixed(2)}</span>
              </header>
              <p>{source.text}</p>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
