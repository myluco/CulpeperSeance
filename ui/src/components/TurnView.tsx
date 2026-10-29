import type { Health, Turn } from "../types";
import { GhostText } from "./GhostText";
import { Summoning } from "./Summoning";
import { VerdictStamp } from "./VerdictStamp";

export function TurnView({ turn, health }: { turn: Turn; health: Health | null }) {
  const speaking = turn.tokens.length > 0;
  const quiet = turn.refusal?.reason === "selfharm";

  return (
    <article className="turn">
      <p className="visitor">{turn.question}</p>
      {turn.pending && !speaking && !turn.refusal && !turn.error ? (
        <Summoning stage={turn.stage} health={health} />
      ) : null}
      {speaking ? <GhostText tokens={turn.tokens} /> : null}
      {turn.refusal ? <p className={quiet ? "refusal quiet" : "refusal"}>{turn.refusal.text}</p> : null}
      {turn.error ? <p className="banner">{turn.error}</p> : null}
      {turn.verdicts.length > 0 ? (
        <section className="veil" aria-label="Beyond the veil">
          <h2>Beyond the veil</h2>
          <div className="stamps">
            {turn.verdicts.map((verdict) => (
              <VerdictStamp key={verdict.herb_id} verdict={verdict} />
            ))}
          </div>
        </section>
      ) : null}
    </article>
  );
}
