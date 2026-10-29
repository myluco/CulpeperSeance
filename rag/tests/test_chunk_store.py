from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from rag.chunk import herb_to_documents, herbs_to_documents, split_text
from rag.config import get_settings
from rag.parse import parse_herbal, write_jsonl
from rag.retriever import load_herbs, retrieve
from rag.store import (
    EmbeddingMismatchError,
    StoreNotBuiltError,
    build_store,
    open_store,
    read_manifest,
    store_is_built,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_herbal.txt"


@pytest.fixture
def herbs():
    from dataclasses import asdict

    return [asdict(h) for h in parse_herbal(FIXTURE.read_text(encoding="utf-8")).herbs]


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CULPEPER_ROOT", str(tmp_path))
    monkeypatch.setenv("EMBED_MODEL", "fake-embed")
    return get_settings()


FAKE = DeterministicFakeEmbedding(size=48)


def test_split_text_respects_limit_and_loses_nothing():
    text = " ".join(f"Sentence number {i} is here." for i in range(200))
    pieces = split_text(text, 300)
    assert all(len(p) <= 300 for p in pieces)
    assert " ".join(pieces).split() == text.split()
    assert split_text("short", 300) == ["short"]
    assert split_text("   ", 300) == []


def test_split_text_hard_splits_a_giant_sentence():
    pieces = split_text("word " * 500, 100)
    assert all(len(p) <= 100 for p in pieces) and len(pieces) > 1


def test_documents_have_prefix_metadata_and_primitive_values(herbs):
    docs = herb_to_documents(herbs[0], max_chars=400)
    assert docs[0].page_content.startswith("Alehoof (also Ground-Ivy), an herb of Venus. Description:")
    for doc in docs:
        assert all(isinstance(v, (str, int, float, bool)) for v in doc.metadata.values())
        assert doc.page_content[doc.metadata["prefix_len"]:] in doc.page_content
    assert {d.metadata["section"] for d in docs} == {"description", "habitat", "virtues"}
    assert len({d.id for d in docs}) == len(docs)


def test_long_sections_are_split_into_parts(herbs):
    herbs[0]["sections"]["virtues"] = "It purges the humours. " * 200
    docs = [d for d in herb_to_documents(herbs[0], max_chars=500) if d.metadata["section"] == "virtues"]
    assert len(docs) > 3
    assert [d.metadata["part"] for d in docs] == list(range(len(docs)))


def test_store_requires_building(settings):
    assert not store_is_built(settings)
    with pytest.raises(StoreNotBuiltError):
        open_store(settings, FAKE)


def test_build_persist_reopen_and_retrieve(herbs, settings):
    docs = herbs_to_documents(herbs, max_chars=400)
    seen = []
    build_store(docs, settings, FAKE, batch_size=3, on_progress=lambda d, t: seen.append((d, t)))
    assert seen[-1] == (len(docs), len(docs))

    manifest = read_manifest(settings)
    assert manifest["embed_model"] == "fake-embed"
    assert manifest["chunks"] == len(docs) and manifest["herbs"] == 4
    assert store_is_built(settings)

    # "reopen in a new process": a fresh store object over the same directory, no re-embedding
    store = open_store(settings, FAKE)
    target = next(d for d in docs if d.metadata["herb_id"] == "balm" and d.metadata["section"] == "virtues")
    hits = retrieve(target.page_content, k=3, settings=settings, store=store, match_names=False)
    assert hits[0].herb == "Balm" and hits[0].section == "virtues"
    assert hits[0].distance == pytest.approx(0.0, abs=1e-4)
    assert hits[0].relevance == pytest.approx(1.0, abs=1e-4)
    assert not hits[0].text.startswith("Balm")  # prefix stripped from the original passage
    assert "cordial" in hits[0].text


def test_retrieve_limits_chunks_per_herb(herbs, settings):
    docs = herbs_to_documents(herbs, max_chars=120)
    build_store(docs, settings, FAKE)
    hits = retrieve("herb", k=6, per_herb=1, settings=settings, store=open_store(settings, FAKE), match_names=False)
    assert len({h.herb_id for h in hits}) == len(hits)


def test_rebuild_with_reset_replaces_contents(herbs, settings):
    build_store(herbs_to_documents(herbs), settings, FAKE)
    build_store(herbs_to_documents(herbs[:1]), settings, FAKE, reset=True)
    assert read_manifest(settings)["herbs"] == 1
    hits = retrieve("anything", k=10, per_herb=10, settings=settings, store=open_store(settings, FAKE), match_names=False)
    assert {h.herb_id for h in hits} == {"alehoof"}


def test_embedding_model_mismatch_is_refused(herbs, settings, monkeypatch):
    build_store(herbs_to_documents(herbs), settings, FAKE)
    monkeypatch.setenv("EMBED_MODEL", "some-other-model")
    with pytest.raises(EmbeddingMismatchError, match="some-other-model"):
        open_store(get_settings(), FAKE)


def test_load_herbs_reads_jsonl(herbs, settings):
    from rag.parse import Herb

    write_jsonl([Herb(**h) for h in herbs], settings.herbs_jsonl)
    assert [h["id"] for h in load_herbs(settings)] == ["alehoof", "asparagus", "balm", "water-betony"]
