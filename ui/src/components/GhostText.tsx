export function GhostText({ tokens }: { tokens: string[] }) {
  return (
    <p className="ghost-text">
      {tokens.map((token, index) => (
        <span key={index} className="ghost-token">
          {token}
        </span>
      ))}
    </p>
  );
}
