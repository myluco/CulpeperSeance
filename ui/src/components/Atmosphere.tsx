import { Specters } from "./Specters";

export function Atmosphere() {
  return (
    <div className="atmosphere" aria-hidden="true">
      <div className="candle" />
      <div className="fog">
        <span />
        <span />
        <span />
      </div>
      <Specters />
    </div>
  );
}
