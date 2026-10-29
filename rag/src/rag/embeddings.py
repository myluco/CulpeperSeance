"""Embedding model factory (Ollama, via LangChain)."""
from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings

from .config import Settings, get_settings


class PrefixedEmbeddings(Embeddings):
    """Adds the task prefixes some retrieval models (nomic, embeddinggemma) expect."""

    def __init__(self, inner: Embeddings, doc_prefix: str = "", query_prefix: str = ""):
        self.inner = inner
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed_documents([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(self.query_prefix + text)


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    settings = settings or get_settings()
    inner = OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_base_url)
    return PrefixedEmbeddings(inner, settings.embed_doc_prefix, settings.embed_query_prefix)
