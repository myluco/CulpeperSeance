"""The Poison Cabinet: the hand-curated verdicts, deadliest first."""

from __future__ import annotations

TAG_ORDER = {"Deadly": 0, "Harmful": 1, "Plausible": 2, "Folklore": 3}


def cabinet(verdicts: dict[str, dict]) -> list[dict]:
    rows = [{"id": herb_id, **entry} for herb_id, entry in verdicts.items()]
    return sorted(rows, key=lambda row: (TAG_ORDER.get(row.get("tag"), 9), row.get("herb", "").lower()))
