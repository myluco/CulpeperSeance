import { useEffect, useState } from "react";

const YAWS = [-34, -16, 12, 32];

export type Heading = { yaw: number; flip: 1 | -1 };

function pick(current: Heading | null): Heading {
  const next = (): Heading => ({
    yaw: YAWS[Math.floor(Math.random() * YAWS.length)],
    flip: Math.random() < 0.5 ? -1 : 1,
  });
  const heading = next();
  if (current && current.yaw === heading.yaw && current.flip === heading.flip) return next();
  return heading;
}

export function useHeading(): Heading {
  const [heading, setHeading] = useState(() => pick(null));

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer = 0;
    const step = () => {
      setHeading((current) => pick(current));
      timer = window.setTimeout(step, 2800 + Math.random() * 3800);
    };
    timer = window.setTimeout(step, 600 + Math.random() * 2200);
    return () => window.clearTimeout(timer);
  }, []);

  return heading;
}
