"""Everything the graph needs from the outside world, injectable for tests."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from rag.config import Settings, get_settings
from rag.retriever import Passage, retrieve

from .verdicts import load_verdicts


@dataclass
class Deps:
    chat_llm: BaseChatModel  # the ghost's voice: warm, streamed
    util_llm: BaseChatModel  # grading and query rewriting: deterministic
    retrieve: Callable[[str], list[Passage]]
    verdicts: dict[str, dict]
    # Relevance = 1 - cosine distance. nomic-embed-text scores cluster between 0.55 and 0.65
    # whether or not the question is about herbs (measured: "sleepless night" 0.63, "capital of
    # France" 0.58), so scores cannot judge relevance and the utility model does. The gates only
    # catch the extremes: at or above `grade_high` accept, below `grade_low` reject.
    grade_high: float = 0.95
    grade_low: float = 0.30
    top_k: int = 4


def default_deps(settings: Settings | None = None) -> Deps:
    settings = settings or get_settings()
    common = {"model": settings.chat_model, "base_url": settings.ollama_base_url}
    return Deps(
        chat_llm=ChatOllama(**common, temperature=0.8),
        util_llm=ChatOllama(**common, temperature=0.0, num_predict=80),
        retrieve=lambda q: retrieve(q, k=4, per_herb=2, settings=settings),
        verdicts=load_verdicts(settings=settings),
        grade_high=float(os.environ.get("GRADE_HIGH", "0.95")),
        grade_low=float(os.environ.get("GRADE_LOW", "0.30")),
    )
