import type { SeanceEvent } from "../types";

function parseFrame(raw: string): SeanceEvent | null {
  const data = raw
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice(6))
    .join("\n");
  if (!data) return null;
  return JSON.parse(data) as SeanceEvent;
}

/** POST /api/ask. EventSource cannot send a JSON body, so the stream is read by hand. */
export async function* ask(question: string, signal: AbortSignal): AsyncGenerator<SeanceEvent> {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => null);
    const message = detail && typeof detail.error === "string" ? detail.error : `The séance failed (${response.status}).`;
    throw new Error(message);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseFrame(part);
      if (event) yield event;
    }
  }
  buffer += decoder.decode();
  const tail = parseFrame(buffer);
  if (tail) yield tail;
}
