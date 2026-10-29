import { useState } from "react";
import { Atmosphere } from "./components/Atmosphere";
import { Cabinet } from "./components/Cabinet";
import { Seance } from "./components/Seance";
import { useHealth } from "./hooks/useHealth";
import type { Health } from "./types";

type Tab = "seance" | "cabinet";

function healthLine(health: Health | null, error: string | null): string {
  if (error) return error;
  if (!health) return "Listening for Ollama";
  if (!health.ollama) return "Ollama is not answering. The spirit cannot be reached.";
  if (!health.store) return "The herbal is not loaded. Run make ingest.";
  return `Ollama is awake · ${health.chat_model}`;
}

export function App() {
  const [tab, setTab] = useState<Tab>("seance");
  const { health, error } = useHealth();
  const warn = Boolean(error) || (health !== null && !health.ok);

  return (
    <>
      <Atmosphere />
      <div className="stage">
        <header className="mast">
          <div>
            <p className="eyebrow">1616–1654</p>
            <h1>The Culpeper Séance</h1>
          </div>
          <nav>
            <button type="button" aria-pressed={tab === "seance"} onClick={() => setTab("seance")}>
              Séance
            </button>
            <button type="button" aria-pressed={tab === "cabinet"} onClick={() => setTab("cabinet")}>
              Poison Cabinet
            </button>
          </nav>
        </header>
        {warn ? (
          <p className="banner" role="status">
            {healthLine(health, error)}
          </p>
        ) : null}
        <div className={tab === "seance" ? "panel" : "panel panel-hidden"}>
          <Seance health={health} />
        </div>
        <div className={tab === "cabinet" ? "panel" : "panel panel-hidden"}>
          <Cabinet />
        </div>
        {warn ? null : (
          <footer className="foot" role="status">
            {healthLine(health, error)}
          </footer>
        )}
      </div>
    </>
  );
}
