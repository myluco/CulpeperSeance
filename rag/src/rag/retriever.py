"""Read side of the RAG layer: what the agent and the Flask server call.

Two retrieval paths, because pure vector search turned out to be a poor fit for this book
(nomic-embed-text scores for on-topic and off-topic questions cluster between 0.55 and 0.65,
and description/habitat chunks full of words like "night" or "hedges" outrank the virtues):

* named herbs: if the question mentions a herb ("Tell me about foxglove"), that herb's own
  chunks are fetched directly, virtues first. No embedding involved.
* everything else: vector search restricted to the "virtues" chunks, which is where the book
  says what each herb is *for*.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever

from .config import Settings, get_settings
from .parse import read_jsonl
from .store import open_store

_STORES: dict[tuple[str, str], Chroma] = {}

NAMED_DISTANCE = 0.2  # stand-in distance for passages fetched by name (no embedding was compared)
# Herb names that are also everyday words and would match by accident.
_STOP_NAMES = {"down"}
_SECTION_RANK = {"virtues": 0, "description": 1, "habitat": 2}


@dataclass(frozen=True)
class Passage:
    """One retrieved chunk of the herbal."""

    text: str  # the original passage, without the title prefix
    herb_id: str
    herb: str
    section: str
    planet: str
    aliases: str
    distance: float  # cosine distance, lower is closer
    named: bool = False  # True if fetched because the question named this herb

    @property
    def relevance(self) -> float:
        return max(0.0, 1.0 - self.distance)


def get_store(settings: Settings | None = None, embeddings: Embeddings | None = None) -> Chroma:
    """Open the persisted store once per process and reuse it."""
    settings = settings or get_settings()
    key = (str(settings.chroma_dir), settings.embed_model)
    if embeddings is not None:
        return open_store(settings, embeddings)
    if key not in _STORES:
        _STORES[key] = open_store(settings)
    return _STORES[key]


def get_retriever(k: int = 4, settings: Settings | None = None) -> VectorStoreRetriever:
    """A plain LangChain retriever, for use in any LangChain/LangGraph chain."""
    return get_store(settings).as_retriever(search_kwargs={"k": k, "filter": {"section": "virtues"}})


# --------------------------------------------------------------------------- herb names


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


class HerbIndex:
    """Finds herb names (and aliases) mentioned in a question.

    Matching ignores case, hyphens, spaces and apostrophes ("fox glove" finds Fox-Glove) and a
    plural "s" ("foxgloves"). Longer phrases win over shorter ones.
    """

    def __init__(self, metadatas: list[dict]):
        self.names: dict[str, str] = {}
        seen: set[str] = set()
        for meta in metadatas:
            herb_id = meta["herb_id"]
            if herb_id in seen:
                continue
            seen.add(herb_id)
            labels = [meta["herb"], *(a.strip() for a in meta.get("aliases", "").split(",") if a.strip())]
            for label in labels:
                key = _norm(label)
                for variant in {key, _singular(key)}:
                    if len(variant) >= 3 and variant not in _STOP_NAMES:
                        self.names.setdefault(variant, herb_id)

    def _lookup(self, candidate: str) -> str | None:
        for form in (candidate, _singular(candidate)):
            if form in self.names:
                return self.names[form]
        return None

    def find(self, query: str, limit: int = 2) -> list[str]:
        tokens = re.findall(r"[a-z0-9]+", query.lower().replace("’", "").replace("'", ""))
        found: list[str] = []
        used: set[int] = set()
        for width in (6, 5, 4, 3, 2, 1):  # the longest herb names run to six words
            for i in range(len(tokens) - width + 1):
                span = range(i, i + width)
                if any(j in used for j in span):
                    continue
                herb_id = self._lookup("".join(tokens[i : i + width]))
                if herb_id and herb_id not in found:
                    found.append(herb_id)
                    used.update(span)
        return found[:limit]


def get_index(store: Chroma) -> HerbIndex:
    index = getattr(store, "_culpeper_index", None)
    if index is None:
        index = HerbIndex(store.get(include=["metadatas"])["metadatas"])
        store._culpeper_index = index  # cached on the store object
    return index


# --------------------------------------------------------------------------- retrieval


def _to_passage(text: str, meta: dict, distance: float, named: bool = False) -> Passage:
    return Passage(
        text=text[int(meta.get("prefix_len", 0)) :],
        herb_id=meta["herb_id"],
        herb=meta["herb"],
        section=meta["section"],
        planet=meta.get("planet", ""),
        aliases=meta.get("aliases", ""),
        distance=distance,
        named=named,
    )


def _named_passages(store: Chroma, herb_id: str, limit: int) -> list[Passage]:
    """A herb's own chunks, best first: virtues, description, more virtues, the rest."""
    data = store.get(where={"herb_id": herb_id}, include=["documents", "metadatas"])

    def rank(row):
        _, meta = row
        section, part = meta["section"], int(meta.get("part", 0))
        if part == 0 and section in ("virtues", "description"):
            return (_SECTION_RANK[section], 0)
        return (2 + _SECTION_RANK.get(section, 9), part)

    rows = sorted(zip(data["documents"], data["metadatas"]), key=rank)
    return [_to_passage(doc, meta, NAMED_DISTANCE, named=True) for doc, meta in rows[:limit]]


def retrieve(
    query: str,
    k: int = 4,
    per_herb: int = 2,
    settings: Settings | None = None,
    store: Chroma | None = None,
    match_names: bool = True,
) -> list[Passage]:
    """Up to ``k`` passages.

    If the question names a herb (and ``match_names``), only that herb's own entry is
    returned: padding it with the nearest unrelated herbs just invites the ghost to
    wander. Otherwise: the closest "virtues" chunks, with at most ``per_herb`` from any one
    herb so one long entry cannot crowd out the others.
    """
    store = store or get_store(settings)

    named_ids = get_index(store).find(query) if match_names else []
    if named_ids:
        per = max(2, k // len(named_ids))
        named = [p for herb_id in named_ids for p in _named_passages(store, herb_id, per)]
        return named[:k]

    passages: list[Passage] = []
    counts: dict[str, int] = {}
    results = store.similarity_search_with_score(query, k=max(k * 4, 8), filter={"section": "virtues"})
    for doc, distance in results:
        herb_id = doc.metadata["herb_id"]
        if counts.get(herb_id, 0) >= per_herb:
            continue
        counts[herb_id] = counts.get(herb_id, 0) + 1
        passages.append(_to_passage(doc.page_content, doc.metadata, float(distance)))
        if len(passages) >= k:
            break
    return passages


def load_herbs(settings: Settings | None = None) -> list[dict]:
    """All parsed herbs (for the Poison Cabinet). Reads herbs.jsonl, no embeddings needed."""
    settings = settings or get_settings()
    return read_jsonl(settings.herbs_jsonl)


def get_herb(herb_id: str, settings: Settings | None = None) -> dict | None:
    return next((h for h in load_herbs(settings) if h["id"] == herb_id), None)
