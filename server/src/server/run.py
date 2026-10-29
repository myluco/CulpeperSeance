"""Process entry: refuse to start when the vector store has not been built."""

from __future__ import annotations

import sys

from rag.config import get_settings
from rag.store import store_is_built

from .app import create_app
from .config import server_bind


def main() -> int:
    settings = get_settings()
    if not store_is_built(settings):
        print(
            f"No vector store found in {settings.chroma_dir}. Run `make ingest` first.",
            file=sys.stderr,
        )
        return 1
    host, port = server_bind()
    create_app(settings).run(host=host, port=port, threaded=True)
    return 0
