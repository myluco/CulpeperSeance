from __future__ import annotations

from typing import TypedDict

from rag.retriever import Passage


class AgentState(TypedDict, total=False):
    question: str
    rewritten_query: str
    off_topic: bool  # rewriter answered NONE: the question is not in the herbal
    attempts: int  # query rewrites used so far (0 or 1)
    passages: list[Passage]
    relevant: bool
    refusal: dict  # {"reason": ..., "text": ...}
    answer: str
    verdicts: list[dict]
