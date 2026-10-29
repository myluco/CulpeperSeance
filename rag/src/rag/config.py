"""Paths and settings shared by every Python package in the project.

Everything is derived from the project root so the ingest script, the agent and the
Flask server all agree on where the data lives. Override with environment variables
(or a `.env` file in the project root).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# rag/src/rag/config.py -> parents[3] is the project root
DEFAULT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(DEFAULT_ROOT / ".env")

GUTENBERG_ID = 49513
GUTENBERG_URLS = (
    f"https://www.gutenberg.org/cache/epub/{GUTENBERG_ID}/pg{GUTENBERG_ID}.txt",
    f"https://www.gutenberg.org/ebooks/{GUTENBERG_ID}.txt.utf-8",
)
SOURCE_LABEL = f"Culpeper's Complete Herbal (Project Gutenberg #{GUTENBERG_ID})"
COLLECTION = "culpeper_herbal"


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    raw_text: Path
    herbs_jsonl: Path
    parse_report: Path
    chroma_dir: Path
    verdicts_json: Path
    ollama_base_url: str
    chat_model: str
    embed_model: str
    embed_doc_prefix: str
    embed_query_prefix: str


def _default_prefixes(model: str) -> tuple[str, str]:
    """Retrieval models trained with task prefixes need them for good results."""
    name = model.lower()
    if name.startswith("nomic-embed-text"):
        return "search_document: ", "search_query: "
    if name.startswith("embeddinggemma"):
        return "title: none | text: ", "task: search result | query: "
    return "", ""


def get_settings() -> Settings:
    """Build settings from the environment. Cheap; call it whenever you need it."""
    root = Path(os.environ.get("CULPEPER_ROOT") or DEFAULT_ROOT).resolve()
    data = root / "data"
    embed_model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    doc_prefix, query_prefix = _default_prefixes(embed_model)
    return Settings(
        root=root,
        data_dir=data,
        raw_text=data / "raw" / f"pg{GUTENBERG_ID}.txt",
        herbs_jsonl=data / "processed" / "herbs.jsonl",
        parse_report=data / "processed" / "parse_report.json",
        chroma_dir=data / "chroma",
        verdicts_json=data / "verdicts.json",
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        chat_model=os.environ.get("CHAT_MODEL", "gemma3:31b-cloud"),
        embed_model=embed_model,
        embed_doc_prefix=os.environ.get("EMBED_DOC_PREFIX", doc_prefix),
        embed_query_prefix=os.environ.get("EMBED_QUERY_PREFIX", query_prefix),
    )
