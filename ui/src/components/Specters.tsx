import { useState } from "react";
import cat from "../assets/cat.png";
import ghost from "../assets/ghost.png";
import witch from "../assets/witch.png";
import { Flyer } from "./Flyer";

const SOURCES = { ghost, witch, cat } as const;

type Kind = keyof typeof SOURCES;

const roster = () =>
  (Object.keys(SOURCES) as Kind[]).flatMap((kind) =>
    Array.from({ length: 2 + Math.floor(Math.random() * 3) }, (_, index) => ({
      id: `${kind}-${index}`,
      kind,
      src: SOURCES[kind],
    })),
  );

export function Specters() {
  const [flyers] = useState(roster);

  return (
    <div className="specters">
      {flyers.map((flyer) => (
        <Flyer key={flyer.id} kind={flyer.kind} src={flyer.src} />
      ))}
    </div>
  );
}
