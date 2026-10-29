"""One agent event, one SSE frame. The event name is the agent's `type`."""

from __future__ import annotations

import json


def encode(event: dict) -> str:
    kind = str(event.get("type") or "message")
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {kind}\ndata: {data}\n\n"
