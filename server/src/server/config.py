"""Where the Flask process listens. The rest of the settings live in `rag.config`."""

from __future__ import annotations

import os


def server_bind() -> tuple[str, int]:
    return os.environ.get("SERVER_HOST", "127.0.0.1"), int(os.environ.get("SERVER_PORT", "5000"))
