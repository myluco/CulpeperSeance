import { useState } from "react";
import { useHerbs } from "../hooks/useHerbs";
import { VerdictStamp } from "./VerdictStamp";

const FILTERS = ["All", "Deadly", "Harmful", "Plausible", "Folklore"];

export function Cabinet() {
  const { herbs, error, loading } = useHerbs();
  const [filter, setFilter] = useState("All");
  const shown = filter === "All" ? herbs : herbs.filter((herb) => herb.tag === filter);

  return (
    <section className="cabinet">
      <header>
        <h2>Poison Cabinet</h2>
        <p>Hand-written modern verdicts. The ghost does not invent these.</p>
      </header>
      <div className="filters" role="tablist" aria-label="Verdict tags">
        {FILTERS.map((tag) => (
          <button key={tag} type="button" aria-pressed={filter === tag} onClick={() => setFilter(tag)}>
            {tag}
          </button>
        ))}
      </div>
      {loading ? <p className="empty">Opening the cabinet…</p> : null}
      {error ? <p className="banner">{error}</p> : null}
      <ul className="cabinet-grid">
        {shown.map((herb) => (
          <li key={herb.id}>
            <VerdictStamp
              verdict={{
                herb_id: herb.id,
                primary: false,
                herb: herb.herb,
                modern_name: herb.modern_name,
                tag: herb.tag,
                toxicity: herb.toxicity,
                summary: herb.summary,
                caution: herb.caution,
              }}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
