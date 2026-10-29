import json

from server.app import create_app
from server.herbs import cabinet
from server.run import main
from server.sse import encode

VERDICTS = {
    "balm": {"herb": "Balm", "modern_name": "Lemon balm", "tag": "Folklore", "toxicity": "low",
             "summary": "A pleasant tea.", "caution": "None."},
    "fox-glove": {"herb": "Fox-Glove", "modern_name": "Foxglove", "tag": "Deadly", "toxicity": "high",
                  "summary": "Deadly.", "caution": "Poisonous."},
    "rue": {"herb": "Rue", "modern_name": "Rue", "tag": "Harmful", "toxicity": "moderate",
            "summary": "Burns the skin.", "caution": "Do not eat."},
}


def fake_ask(question):
    yield {"type": "status", "stage": "searching"}
    yield {"type": "token", "text": "Balm\nhelps."}
    yield {"type": "verdict", "verdicts": []}
    yield {"type": "done"}
    assert question == "sleep"


def parse_sse(body: str) -> list[tuple[str, dict]]:
    frames = []
    for block in body.strip().split("\n\n"):
        kind, data = "", {}
        for line in block.splitlines():
            if line.startswith("event: "):
                kind = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        frames.append((kind, data))
    return frames


def app():
    return create_app(
        ask_fn=fake_ask,
        ollama_probe=lambda: True,
        store_probe=lambda: True,
        verdicts=VERDICTS,
    )


def test_ask_streams_typed_events_and_ends_with_done():
    resp = app().test_client().post("/api/ask", json={"question": "sleep"})
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    assert resp.headers["X-Accel-Buffering"] == "no"
    assert resp.headers["Cache-Control"] == "no-cache"
    body = resp.get_data(as_text=True)
    frames = parse_sse(body)
    assert [kind for kind, _ in frames] == ["status", "token", "verdict", "done"]
    assert frames[-1][1]["type"] == "done"
    assert frames[1][1]["text"] == "Balm\nhelps."


def test_ask_rejects_a_body_without_a_string_question():
    client = app().test_client()
    assert client.post("/api/ask", json={}).status_code == 400
    assert client.post("/api/ask", json={"question": 3}).status_code == 400
    assert client.post("/api/ask", data="sleep").status_code == 400


def test_health_is_ok_only_when_ollama_and_the_store_are_up():
    up = create_app(ask_fn=fake_ask, ollama_probe=lambda: True, store_probe=lambda: True, verdicts={})
    body = up.test_client().get("/api/health").get_json()
    assert body["ok"] is True and body["ollama"] is True and body["store"] is True

    down = create_app(ask_fn=fake_ask, ollama_probe=lambda: False, store_probe=lambda: True, verdicts={})
    resp = down.test_client().get("/api/health")
    assert resp.status_code == 503 and resp.get_json()["ok"] is False


def test_herbs_lists_the_cabinet_deadliest_first():
    herbs = app().test_client().get("/api/herbs").get_json()["herbs"]
    assert [h["id"] for h in herbs] == ["fox-glove", "rue", "balm"]
    assert herbs[0]["tag"] == "Deadly" and herbs[0]["caution"] == "Poisonous."


def test_cabinet_orders_tags_then_name():
    rows = cabinet({"z": {"herb": "Zebra", "tag": "Folklore"}, "a": {"herb": "Aconite", "tag": "Deadly"}})
    assert [row["id"] for row in rows] == ["a", "z"]


def test_encode_keeps_each_event_on_one_data_line():
    frame = encode({"type": "token", "text": "line\nbreak"})
    assert frame == 'event: token\ndata: {"type": "token", "text": "line\\nbreak"}\n\n'


def test_main_refuses_to_start_without_a_store(monkeypatch, capsys):
    monkeypatch.setattr("server.run.store_is_built", lambda settings: False)
    assert main() == 1
    assert "make ingest" in capsys.readouterr().err


def test_main_serves_when_the_store_exists(monkeypatch):
    called = {}

    class Dummy:
        def run(self, **kwargs):
            called.update(kwargs)

    monkeypatch.setattr("server.run.store_is_built", lambda settings: True)
    monkeypatch.setattr("server.run.create_app", lambda settings: Dummy())
    assert main() == 0
    assert called["threaded"] is True and called["host"] and called["port"]
