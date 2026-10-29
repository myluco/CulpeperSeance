"""Turn parsed herbs into retrieval-sized LangChain Documents.

Chunking is deliberately separate from parsing: herbs.jsonl is the canonical file, and
chunks are derived from it at ingest time, so chunk size can change without re-parsing.
Every chunk starts with the herb's name (and planet) so it still makes sense, and
embeds well, when retrieved on its own.
"""
from __future__ import annotations

import re

from langchain_core.documents import Document

from .config import SOURCE_LABEL

DEFAULT_MAX_CHARS = 1200
_SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+")


def split_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Pack sentences into pieces of at most ``max_chars`` (hard-splitting giant sentences)."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut])
            sentence = sentence[cut:].lstrip()
        if current and len(current) + 1 + len(sentence) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence
    if current:
        pieces.append(current)
    return pieces


def _title(herb: dict) -> str:
    title = herb["name"]
    if herb.get("aliases"):
        title += f" (also {', '.join(herb['aliases'])})"
    if herb.get("planet"):
        title += f", an herb of {herb['planet']}"
    return title


def herb_to_documents(herb: dict, max_chars: int = DEFAULT_MAX_CHARS) -> list[Document]:
    s = herb.get("sections", {})
    habitat = " ".join(
        f"{label}: {s[key]}" for key, label in (("place", "Place"), ("time", "Time")) if s.get(key)
    )
    plan = [
        ("description", "Description", " ".join(x for x in (s.get("intro"), s.get("description")) if x)),
        ("habitat", "Place and time", habitat),
        ("virtues", "Government and virtues", s.get("virtues", "")),
    ]
    title = _title(herb)
    docs: list[Document] = []
    for key, label, text in plan:
        prefix = f"{title}. {label}: "
        for part, piece in enumerate(split_text(text, max_chars)):
            docs.append(
                Document(
                    id=f"{herb['id']}:{key}:{part}",
                    page_content=prefix + piece,
                    metadata={
                        "herb_id": herb["id"],
                        "herb": herb["name"],
                        "aliases": ", ".join(herb.get("aliases", [])),
                        "planet": herb.get("planet", ""),
                        "section": key,
                        "part": part,
                        # lets callers recover the original passage without the title prefix
                        "prefix_len": len(prefix),
                        "source": SOURCE_LABEL,
                    },
                )
            )
    return docs


def herbs_to_documents(herbs: list[dict], max_chars: int = DEFAULT_MAX_CHARS) -> list[Document]:
    return [doc for herb in herbs for doc in herb_to_documents(herb, max_chars)]
