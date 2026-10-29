"""Curated modern verdicts. Pure lookup: toxicity claims are never model-generated."""
from __future__ import annotations

import json
from pathlib import Path

from rag.config import Settings, get_settings
from rag.retriever import Passage

TAGS = ("Folklore", "Plausible", "Harmful", "Deadly")
TOXICITY = ("low", "moderate", "high")


def load_verdicts(path: Path | None = None, settings: Settings | None = None) -> dict[str, dict]:
    """Read data/verdicts.json. Returns {} (not an error) if the file is absent."""
    path = path or (settings or get_settings()).verdicts_json
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("verdicts", {})


def verdicts_for(passages: list[Passage], verdicts: dict[str, dict], limit: int = 3) -> list[dict]:
    """One verdict per distinct herb among the passages, best-matching herb first.

    Every retrieved herb with a verdict is returned, not just the top one: the answer may
    draw on any of the passages, and a deadly plant must not go unflagged because a milder
    one ranked first.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for p in passages:
        if p.herb_id in seen:
            continue
        seen.add(p.herb_id)
        entry = verdicts.get(p.herb_id)
        if entry:
            out.append({"herb_id": p.herb_id, "primary": not out and p is passages[0], **entry})
        if len(out) >= limit:
            break
    return out
