"""Is Ollama answering, and is the persisted Chroma store on disk?"""

from __future__ import annotations

import urllib.error
import urllib.request


def ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    url = base_url.rstrip("/") + "/api/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def health_body(ollama: bool, store: bool, chat_model: str) -> tuple[dict, int]:
    ok = ollama and store
    body = {"ok": ok, "ollama": ollama, "store": store, "chat_model": chat_model}
    return body, 200 if ok else 503
