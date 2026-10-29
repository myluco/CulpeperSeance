from dataclasses import asdict
from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from rag.chunk import herbs_to_documents
from rag.config import get_settings
from rag.parse import parse_herbal
from rag.retriever import NAMED_DISTANCE, HerbIndex, get_index, retrieve
from rag.store import build_store, open_store

FIXTURE = Path(__file__).parent / "fixtures" / "sample_herbal.txt"
FAKE = DeterministicFakeEmbedding(size=48)


def meta(herb_id, herb, aliases=""):
    return {"herb_id": herb_id, "herb": herb, "aliases": aliases}


INDEX = HerbIndex(
    [
        meta("fox-glove", "Fox-Glove"),
        meta("alehoof", "Alehoof", "Ground-Ivy"),
        meta("water-betony", "Water Betony"),
        meta("roses", "Roses"),
        meta("down", "Down", "Cotton-Thistle"),
        meta("black-alder-tree", "Black Alder-Tree"),
        meta("st-john-s-wort", "St. John’s Wort"),
        meta("lily-of-the-valley", "Lily Of The Valley"),
        meta("queen-of-the-meadows", "Queen Of The Meadows"),
    ]
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Tell me about foxglove", ["fox-glove"]),
        ("what is FOX-GLOVE good for", ["fox-glove"]),
        ("fox glove?", ["fox-glove"]),
        ("foxgloves in the garden", ["fox-glove"]),
        ("Is ground ivy useful", ["alehoof"]),
        ("tell me of alehoof and foxglove", ["alehoof", "fox-glove"]),
        ("water betony for wounds", ["water-betony"]),
        ("a bouquet of rose", ["roses"]),
        ("what about St John's wort?", ["st-john-s-wort"]),
        ("the black alder tree", ["black-alder-tree"]),
        ("cotton thistle", ["down"]),
        ("is lily of the valley poisonous", ["lily-of-the-valley"]),
        ("the queen of the meadows", ["queen-of-the-meadows"]),
    ],
)
def test_herb_names_are_found(query, expected):
    assert INDEX.find(query) == expected


@pytest.mark.parametrize(
    "query",
    ["Something for a sleepless night?", "go down the road", "capital of France", "", "how do I get warm"],
)
def test_no_false_matches(query):
    assert INDEX.find(query) == []


def test_find_limits_the_number_of_herbs():
    assert len(INDEX.find("alehoof foxglove roses", limit=2)) == 2


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CULPEPER_ROOT", str(tmp_path))
    monkeypatch.setenv("EMBED_MODEL", "fake-embed")
    settings = get_settings()
    herbs = [asdict(h) for h in parse_herbal(FIXTURE.read_text(encoding="utf-8")).herbs]
    build_store(herbs_to_documents(herbs, max_chars=300), settings, FAKE)
    return open_store(settings, FAKE)


def test_index_is_built_from_the_store_and_cached(store):
    index = get_index(store)
    assert index.find("tell me about alehoof") == ["alehoof"]
    assert index.find("also called ground ivy") == ["alehoof"]
    assert get_index(store) is index


def test_named_herb_returns_its_own_entry_virtues_first(store):
    hits = retrieve("Tell me about alehoof", k=4, store=store)
    assert 3 <= len(hits) <= 4 and all(h.herb == "Alehoof" and h.named for h in hits)
    assert (hits[0].section, hits[1].section) == ("virtues", "description")
    assert "dominion of Venus" in hits[0].text
    assert hits[0].distance == NAMED_DISTANCE
    assert not hits[0].text.startswith("Alehoof")  # title prefix stripped


def test_named_herb_is_not_padded_with_unrelated_herbs(store):
    hits = retrieve("Tell me about balm", k=4, store=store)
    assert {h.herb for h in hits} == {"Balm"}


def test_two_named_herbs_share_the_slots(store):
    hits = retrieve("balm or alehoof?", k=4, store=store)
    assert {h.herb for h in hits} == {"Balm", "Alehoof"}
    assert sum(h.herb == "Balm" for h in hits) == 2


def test_questions_without_a_name_search_only_the_virtues(store):
    hits = retrieve("Something for a sleepless night?", k=4, store=store)
    assert hits and all(h.section == "virtues" and not h.named for h in hits)
    assert len({h.herb_id for h in hits}) == len(hits) or max(
        sum(x.herb_id == h.herb_id for x in hits) for h in hits) <= 2


def test_a_named_herb_wins_over_a_vague_rest_of_the_question(store):
    hits = retrieve("balm and something to cool the blood", k=4, store=store)
    assert {h.herb for h in hits} == {"Balm"} and all(h.named for h in hits)


def test_match_names_can_be_turned_off(store):
    hits = retrieve("Tell me about alehoof", k=4, store=store, match_names=False)
    assert all(not h.named and h.section == "virtues" for h in hits)
