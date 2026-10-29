import { useEffect, useRef } from "react";
import { planJourney, type Journey } from "./journey";

const FORWARD = { ghost: 0, witch: 180, cat: 180 } as const;

type Kind = keyof typeof FORWARD;

const face = (node: HTMLSpanElement, lean: number, flip: 1 | -1) => {
  const image = node.querySelector("img");
  if (!image) return;
  image.style.rotate = `${lean}deg`;
  image.style.scale = `${flip} 1`;
};

const play = (node: HTMLSpanElement, journey: Journey) => {
  face(node, journey.lean, journey.flip);
  if (journey.mode === "line") {
    node.style.offsetPath = "none";
    node.style.offsetRotate = "0deg";
    return node.animate(
      [
        { transform: `translate(${journey.from.x}px, ${journey.from.y}px)` },
        { transform: `translate(${journey.to.x}px, ${journey.to.y}px)` },
      ],
      { duration: journey.ms, easing: "linear", fill: "forwards" },
    );
  }
  node.style.transform = "none";
  node.style.offsetPath = journey.path;
  node.style.offsetRotate = "0deg";
  const end = journey.clockwise ? journey.start + 100 : journey.start - 100;
  return node.animate(
    [{ offsetDistance: `${journey.start}%` }, { offsetDistance: `${end}%` }],
    { duration: journey.ms, easing: "linear", fill: "forwards" },
  );
};

export function Flyer({ kind, src }: { kind: Kind; src: string }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const box = () => node.parentElement?.getBoundingClientRect();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduced) {
      const stage = box();
      if (!stage) return;
      const journey = planJourney(stage.width, stage.height, FORWARD[kind]);
      if (journey.mode === "line") {
        node.style.transform = `translate(${(journey.from.x + journey.to.x) / 2}px, ${(journey.from.y + journey.to.y) / 2}px)`;
      } else {
        node.style.offsetPath = journey.path;
        node.style.offsetDistance = `${journey.start}%`;
      }
      face(node, journey.lean, journey.flip);
      return;
    }

    let stopped = false;
    let flight: Animation | null = null;

    const launch = () => {
      if (stopped) return;
      const stage = box();
      if (!stage || stage.width < 10) {
        window.requestAnimationFrame(launch);
        return;
      }
      if (flight) {
        flight.onfinish = null;
        flight.cancel();
      }
      flight = play(node, planJourney(stage.width, stage.height, FORWARD[kind]));
      flight.onfinish = () => {
        if (!stopped) launch();
      };
    };

    launch();
    return () => {
      stopped = true;
      if (flight) flight.onfinish = null;
      flight?.cancel();
    };
  }, [kind]);

  return (
    <span ref={ref} className={`specter specter-${kind}`}>
      <img src={src} alt="" />
    </span>
  );
}
