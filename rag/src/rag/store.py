"""Persistent Chroma vector store: build once, reopen forever.

``build_store`` embeds documents and writes the index (plus a small manifest recording
which embedding model made it) into data/chroma/. ``open_store`` just reopens it, with
no re-embedding, and refuses to run against an index built by a different embedding
model, because mixing models silently ruins retrieval.
"""
from __future__ import annotations

import json
import time
from typing import Callable

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .config import COLLECTION, SOURCE_LABEL, Settings, get_settings
from .embeddings import get_embeddings


class StoreNotBuiltError(RuntimeError):
    """The vector store has not been built yet."""


class EmbeddingMismatchError(RuntimeError):
    """The store was built with a different embedding model than the one configured."""


def _client(settings: Settings) -> chromadb.api.ClientAPI:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _manifest_path(settings: Settings):
    return settings.chroma_dir / "manifest.json"


def read_manifest(settings: Settings | None = None) -> dict | None:
    settings = settings or get_settings()
    path = _manifest_path(settings)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def store_is_built(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if read_manifest(settings) is None:
        return False
    try:
        return _client(settings).get_collection(COLLECTION).count() > 0
    except Exception:  # collection missing or unreadable
        return False


def build_store(
    documents: list[Document],
    settings: Settings | None = None,
    embeddings: Embeddings | None = None,
    reset: bool = False,
    batch_size: int = 64,
    on_progress: Callable[[int, int], None] | None = None,
) -> Chroma:
    """Embed ``documents`` into the persistent collection. ``reset`` drops it first."""
    settings = settings or get_settings()
    embeddings = embeddings or get_embeddings(settings)
    client = _client(settings)
    if reset:
        try:
            client.delete_collection(COLLECTION)
        except Exception:  # nothing to delete
            pass
    store = Chroma(
        client=client,
        collection_name=COLLECTION,
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine"},
    )
    total = len(documents)
    for start in range(0, total, batch_size):
        batch = documents[start : start + batch_size]
        store.add_documents(batch, ids=[d.id for d in batch])
        if on_progress:
            on_progress(min(start + batch_size, total), total)

    _manifest_path(settings).write_text(
        json.dumps(
            {
                "embed_model": settings.embed_model,
                "doc_prefix": settings.embed_doc_prefix,
                "chunks": total,
                "herbs": len({d.metadata.get("herb_id") for d in documents}),
                "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "source": SOURCE_LABEL,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return store


def open_store(settings: Settings | None = None, embeddings: Embeddings | None = None) -> Chroma:
    """Reopen the persisted store. Raises if it is missing or was built with another model."""
    settings = settings or get_settings()
    manifest = read_manifest(settings)
    if manifest is None or not store_is_built(settings):
        raise StoreNotBuiltError(
            f"No vector store found in {settings.chroma_dir}. Run `make ingest` first."
        )
    if manifest.get("embed_model") != settings.embed_model:
        raise EmbeddingMismatchError(
            f"The store was built with '{manifest.get('embed_model')}' but EMBED_MODEL is "
            f"'{settings.embed_model}'. Set EMBED_MODEL back, or run `make ingest-rebuild`."
        )
    return Chroma(
        client=_client(settings),
        collection_name=COLLECTION,
        embedding_function=embeddings or get_embeddings(settings),
    )
