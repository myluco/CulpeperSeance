"""Public entry point: `ask(question)` yields typed events, ending with `done`.

Event types: status, sources, token, verdict, refusal, error, done.
"""
from __future__ import annotations

import threading
from typing import Iterator

from .deps import Deps, default_deps
from .graph import build_graph

MAX_QUESTION_CHARS = 500

_lock = threading.Lock()
_default_graph = None


def get_graph(deps: Deps | None = None):
    """Build the graph for `deps`, or reuse one default graph for the whole process."""
    global _default_graph
    if deps is not None:
        return build_graph(deps)
    with _lock:
        if _default_graph is None:
            _default_graph = build_graph(default_deps())
        return _default_graph


def friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc)
    if "Connect" in name or "connection" in text.lower() or "refused" in text.lower():
        return "The spirit cannot be reached. Is Ollama running, and is the chat model available?"
    if "not found" in text.lower():
        return f"The spirit's vessel is missing: {text}"
    return f"The séance was disturbed: {text or name}"


def ask(question: str, deps: Deps | None = None) -> Iterator[dict]:
    question = " ".join((question or "").split())[:MAX_QUESTION_CHARS]
    if not question:
        yield {"type": "error", "message": "Ask the spirit something first."}
        yield {"type": "done"}
        return
    try:
        graph = get_graph(deps)
        yield from graph.stream({"question": question, "attempts": 0}, stream_mode="custom")
    except Exception as exc:  # noqa: BLE001 - surface any failure as an event, never a crash
        yield {"type": "error", "message": friendly_error(exc)}
    yield {"type": "done"}
