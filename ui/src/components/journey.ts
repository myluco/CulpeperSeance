export type Point = { x: number; y: number };

const EDGES = ["left", "right", "top", "bottom"] as const;
type Edge = (typeof EDGES)[number];

const OFFSCREEN = 220;
const PATTERNS = ["across", "along", "corner", "around", "loop"] as const;

const pace = () => 30 + Math.random() * 50;

const duration = (distance: number) => Math.round((distance / pace()) * 1000);

const corners = (width: number, height: number): Point[] => [
  { x: 0, y: 0 },
  { x: width, y: 0 },
  { x: width, y: height },
  { x: 0, y: height },
];

const otherThan = (length: number, index: number) => {
  const pick = Math.floor(Math.random() * (length - 1));
  return pick >= index ? pick + 1 : pick;
};

const extend = (from: Point, to: Point) => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  return {
    from: { x: from.x - (dx / length) * OFFSCREEN, y: from.y - (dy / length) * OFFSCREEN },
    to: { x: to.x + (dx / length) * OFFSCREEN, y: to.y + (dy / length) * OFFSCREEN },
    dx,
    dy,
  };
};

const ellipseLength = (rx: number, ry: number) => {
  const h = ((rx - ry) ** 2) / ((rx + ry) ** 2 || 1);
  return Math.PI * (rx + ry) * (1 + (3 * h) / (10 + Math.sqrt(Math.max(0, 4 - 3 * h))));
};

const LEAN = 32;

const upright = (dx: number, dy: number, facesLeft: boolean) => {
  const lean = Math.max(-LEAN, Math.min(LEAN, (Math.atan2(dy, Math.abs(dx) || 1) * 180) / Math.PI));
  const flip: 1 | -1 = dx < 0 === facesLeft ? 1 : -1;
  return { lean, flip };
};

export type Journey =
  | { mode: "line"; from: Point; to: Point; ms: number; lean: number; flip: 1 | -1 }
  | {
      mode: "orbit";
      path: string;
      start: number;
      clockwise: boolean;
      ms: number;
      lean: number;
      flip: 1 | -1;
      point: Point;
    };

const line = (from: Point, to: Point, forward: number): Journey => {
  const crossed = extend(from, to);
  const pose = upright(crossed.dx, crossed.dy, forward >= 90);
  return {
    mode: "line",
    from: crossed.from,
    to: crossed.to,
    ms: duration(Math.hypot(crossed.dx, crossed.dy)),
    ...pose,
  };
};

const eitherWay = (from: Point, to: Point, forward: number) =>
  Math.random() < 0.5 ? line(from, to, forward) : line(to, from, forward);

const across = (width: number, height: number, forward: number) => {
  if (Math.random() < 0.5) {
    const y = height * (0.15 + Math.random() * 0.7);
    return eitherWay({ x: 0, y }, { x: width, y }, forward);
  }
  const x = width * (0.15 + Math.random() * 0.7);
  return eitherWay({ x, y: 0 }, { x, y: height }, forward);
};

const along = (width: number, height: number, forward: number) => {
  const inset = 56;
  const edge: Edge = EDGES[Math.floor(Math.random() * EDGES.length)];
  if (edge === "top") return eitherWay({ x: 0, y: inset }, { x: width, y: inset }, forward);
  if (edge === "bottom") return eitherWay({ x: 0, y: height - inset }, { x: width, y: height - inset }, forward);
  if (edge === "left") return eitherWay({ x: inset, y: 0 }, { x: inset, y: height }, forward);
  return eitherWay({ x: width - inset, y: 0 }, { x: width - inset, y: height }, forward);
};

const corner = (width: number, height: number, forward: number) => {
  const points = corners(width, height);
  const start = Math.floor(Math.random() * points.length);
  const end = Math.random() < 0.5 ? (start + 2) % points.length : otherThan(points.length, start);
  return line(points[start], points[end], forward);
};

const orbit = (width: number, height: number, forward: number, around: boolean): Journey => {
  const rx = width * (around ? 0.42 : 0.16 + Math.random() * 0.12);
  const ry = height * (around ? 0.36 : 0.14 + Math.random() * 0.1);
  const cx = around ? width / 2 : width * (0.28 + Math.random() * 0.44);
  const cy = around ? height / 2 : height * (0.28 + Math.random() * 0.44);
  const start = Math.random() * 100;
  const clockwise = Math.random() < 0.5;
  const theta = (start / 100) * Math.PI * 2;
  const dx = -rx * Math.sin(theta);
  const dy = ry * Math.cos(theta);
  const pose = upright(clockwise ? dx : -dx, clockwise ? dy : -dy, forward >= 90);
  return {
    mode: "orbit",
    path: `ellipse(${rx}px ${ry}px at ${cx}px ${cy}px)`,
    start,
    clockwise,
    ms: duration(ellipseLength(rx, ry)),
    ...pose,
    point: { x: cx + rx * Math.cos(theta), y: cy + ry * Math.sin(theta) },
  };
};

export const planJourney = (width: number, height: number, forward: number): Journey => {
  const pattern = PATTERNS[Math.floor(Math.random() * PATTERNS.length)];
  if (pattern === "across") return across(width, height, forward);
  if (pattern === "along") return along(width, height, forward);
  if (pattern === "corner") return corner(width, height, forward);
  if (pattern === "around") return orbit(width, height, forward, true);
  return orbit(width, height, forward, false);
};
