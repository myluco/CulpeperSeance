"""App factory. Routes call the agent; they never embed the book or open a model themselves."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from flask import Flask, Response, request

from agent import ask
from agent.verdicts import load_verdicts
from rag.config import Settings, get_settings
from rag.store import store_is_built

from .health import health_body, ollama_reachable
from .herbs import cabinet
from .sse import encode


def create_app(
    settings: Settings | None = None,
    *,
    ask_fn: Callable[[str], Iterator[dict]] | None = None,
    ollama_probe: Callable[[], bool] | None = None,
    store_probe: Callable[[], bool] | None = None,
    verdicts: dict[str, dict] | None = None,
) -> Flask:
    settings = settings or get_settings()
    ask_fn = ask_fn or ask
    ollama_probe = ollama_probe or (lambda: ollama_reachable(settings.ollama_base_url))
    store_probe = store_probe or (lambda: store_is_built(settings))
    if verdicts is None:
        verdicts = load_verdicts(settings=settings)

    app = Flask("server")

    @app.get("/api/health")
    def health():
        body, status = health_body(ollama_probe(), store_probe(), settings.chat_model)
        return body, status

    @app.get("/api/herbs")
    def herbs():
        return {"herbs": cabinet(verdicts)}

    @app.post("/api/ask")
    def ask_route():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("question"), str):
            return {"error": 'Send JSON {"question": "..."}.'}, 400
        question = payload["question"]

        def events():
            for event in ask_fn(question):
                yield encode(event)

        return Response(
            events(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return app
