import { useEffect, useRef, useState } from "react";
import { useSeance } from "../hooks/useSeance";
import type { Health } from "../types";
import { Composer } from "./Composer";
import { Grimoire } from "./Grimoire";
import { TurnView } from "./TurnView";

type Page = "summon" | "grimoire";

export function Seance({ health }: { health: Health | null }) {
  const { turns, asking, submit } = useSeance();
  const [page, setPage] = useState<Page>("summon");
  const [selected, setSelected] = useState<string | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const active = turns.find((turn) => turn.id === selected) ?? turns[turns.length - 1];

  useEffect(() => {
    const latest = turns[turns.length - 1];
    if (latest) setSelected(latest.id);
  }, [turns.length]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [turns]);

  return (
    <div className="seance">
      <nav className="view-tabs" aria-label="Séance pages">
        <button type="button" aria-pressed={page === "summon"} onClick={() => setPage("summon")}>
          Summon
        </button>
        <button type="button" aria-pressed={page === "grimoire"} onClick={() => setPage("grimoire")}>
          Grimoire
        </button>
      </nav>
      <section className={page === "summon" ? "circle" : "circle panel-hidden"}>
        <div className="log" ref={log}>
          {turns.length === 0 ? (
            <p className="welcome">
              The candle is lit. Ask Nicholas Culpeper of a sleepless night, of foxglove, or of a star that rules
              an herb: the Sun, the Moon, Mercury, Venus, Mars, Jupiter, or Saturn. He will answer only from the
              pages he is shown.
            </p>
          ) : (
            turns.map((turn) => <TurnView key={turn.id} turn={turn} health={health} />)
          )}
        </div>
        <Composer asking={asking} onAsk={submit} />
      </section>
      <div className={page === "grimoire" ? "grimoire-page" : "grimoire-page panel-hidden"}>
        <Grimoire sources={active?.sources ?? []} />
      </div>
    </div>
  );
}
