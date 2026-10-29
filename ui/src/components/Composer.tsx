import { FormEvent, useState } from "react";

export function Composer({ asking, onAsk }: { asking: boolean; onAsk: (question: string) => void }) {
  const [question, setQuestion] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    onAsk(trimmed);
    setQuestion("");
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question">Ask the spirit</label>
      <textarea
        id="question"
        rows={2}
        value={question}
        placeholder="An herb, an ailment, or the star that rules it"
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
      />
      <button type="submit" disabled={asking || question.trim().length === 0}>
        {asking ? "Summoning" : "Summon"}
      </button>
    </form>
  );
}
