import json
import re

import pytest
from rag.config import get_settings
from rag.retriever import Passage

from agent.verdicts import TAGS, TOXICITY, load_verdicts, verdicts_for

REAL = get_settings().verdicts_json
REQUIRED = ("herb", "modern_name", "tag", "toxicity", "summary", "caution")


@pytest.fixture(scope="module")
def verdicts():
    return load_verdicts(REAL)


def test_file_loads_and_has_enough_entries(verdicts):
    assert len(verdicts) >= 30


def test_every_entry_is_complete_and_uses_known_values(verdicts):
    for herb_id, entry in verdicts.items():
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", herb_id), herb_id
        for field in REQUIRED:
            assert isinstance(entry.get(field), str) and entry[field].strip(), f"{herb_id}.{field}"
        assert entry["tag"] in TAGS, herb_id
        assert entry["toxicity"] in TOXICITY, herb_id
        assert len(entry["summary"]) <= 400 and len(entry["caution"]) <= 200, herb_id


def test_tags_agree_with_toxicity(verdicts):
    for herb_id, entry in verdicts.items():
        if entry["tag"] == "Deadly":
            assert entry["toxicity"] == "high", herb_id
        if entry["toxicity"] == "high":
            assert entry["tag"] in ("Deadly", "Harmful"), herb_id
        if entry["tag"] == "Harmful":
            assert entry["toxicity"] in ("moderate", "high"), herb_id


def test_the_famous_poisons_are_all_flagged_deadly(verdicts):
    for herb_id in ("fox-glove", "hemlock", "henbane", "black-hellebore", "lily-of-the-valley"):
        assert verdicts[herb_id]["tag"] == "Deadly", herb_id


def test_meta_documents_every_tag():
    meta = json.loads(REAL.read_text(encoding="utf-8"))["_meta"]
    assert set(meta["tags"]) == set(TAGS)


def test_keys_match_real_herb_ids_when_the_parsed_herbs_exist(verdicts):
    herbs = get_settings().herbs_jsonl
    if not herbs.exists():
        pytest.skip("run `make ingest` first to check ids against data/processed/herbs.jsonl")
    ids = {json.loads(line)["id"] for line in herbs.read_text(encoding="utf-8").splitlines() if line.strip()}
    assert sorted(set(verdicts) - ids) == []


def test_missing_file_gives_no_verdicts(tmp_path):
    assert load_verdicts(tmp_path / "nope.json") == {}


def test_verdicts_for_respects_the_limit():
    ps = [Passage("t", f"h{i}", f"H{i}", "virtues", "", "", 0.1) for i in range(5)]
    table = {f"h{i}": {"tag": "Folklore"} for i in range(5)}
    assert [v["herb_id"] for v in verdicts_for(ps, table, limit=2)] == ["h0", "h1"]
