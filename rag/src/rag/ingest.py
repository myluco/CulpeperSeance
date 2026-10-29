"""One-time ingest: download -> parse -> chunk -> embed -> persist.

    python -m rag.ingest                 build everything if the store does not exist yet
    python -m rag.ingest --rebuild       re-embed from data/processed/herbs.jsonl (no re-parse)
    python -m rag.ingest --reparse       re-parse data/raw (no download) and re-embed
    python -m rag.ingest --redownload    fetch the book again, then --reparse
    python -m rag.ingest --parse-only    stop after writing herbs.jsonl and the parse report
                                         (`make parse` = --reparse --parse-only: fast, no Ollama)
    python -m rag.ingest --limit 20      embed only the first 20 herbs (quick smoke test)
"""
from __future__ import annotations

import argparse
import json
import sys

import httpx

from .chunk import herbs_to_documents
from .config import Settings, get_settings
from .download import DownloadError, download
from .parse import build_report, parse_herbal, read_jsonl, write_jsonl
from .store import build_store, store_is_built


class IngestError(RuntimeError):
    pass


def _say(msg: str) -> None:
    print(msg, flush=True)


def check_ollama(settings: Settings) -> None:
    """Fail early, with advice, if Ollama or the embedding model is not available."""
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - any failure means "not reachable"
        raise IngestError(
            f"Cannot reach Ollama at {settings.ollama_base_url} ({exc}).\n"
            "Start it (`ollama serve`) and try again."
        ) from exc
    names = [m.get("name", "") for m in response.json().get("models", [])]
    wanted = settings.embed_model
    if not any(n == wanted or n == f"{wanted}:latest" or n.startswith(f"{wanted}:") for n in names):
        raise IngestError(
            f"Embedding model '{wanted}' is not installed. Run: ollama pull {wanted}"
        )


def parse_book(settings: Settings, reparse: bool, redownload: bool = False) -> list[dict]:
    """Return the canonical herb records, parsing the book only if needed."""
    if settings.herbs_jsonl.exists() and not reparse:
        herbs = read_jsonl(settings.herbs_jsonl)
        _say(f"Using existing {settings.herbs_jsonl.relative_to(settings.root)} ({len(herbs)} herbs)")
        return herbs

    _say("Fetching the herbal (skipped if already in data/raw)...")
    path = download(settings, force=redownload)
    _say(f"Parsing {path.name}...")
    result = parse_herbal(path.read_text(encoding="utf-8", errors="replace"))
    if not result.herbs:
        raise IngestError("The parser found no herbs. Check the file and rag/src/rag/parse.py.")
    write_jsonl(result.herbs, settings.herbs_jsonl)
    report = build_report(result)
    settings.parse_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _say(
        f"  {report['herbs']} herbs ({report['with_virtues']} with virtues, "
        f"{report['with_planet']} with a planet)"
    )
    _say(f"  dropped headings by region: {report['dropped_by_region']}")
    if report["dropped_main"]:
        _say(f"  ! {len(report['dropped_main'])} headings dropped from the herb region; see the report")
    if report["kept_without_labels"]:
        _say(f"  kept without Descript/Government labels: {', '.join(report['kept_without_labels'])}")
    _say(f"  report: {settings.parse_report.relative_to(settings.root)}")
    return [h.__dict__ for h in result.herbs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag.ingest", description=__doc__.split("\n")[0])
    parser.add_argument("--rebuild", action="store_true", help="re-embed even if a store exists")
    parser.add_argument("--reparse", action="store_true", help="re-parse data/raw (no download)")
    parser.add_argument("--redownload", action="store_true", help="fetch the book again, then re-parse")
    parser.add_argument("--parse-only", action="store_true", help="skip embedding")
    parser.add_argument("--limit", type=int, default=0, help="embed only the first N herbs")
    args = parser.parse_args(argv)
    args.reparse = args.reparse or args.redownload

    settings = get_settings()
    try:
        herbs = parse_book(settings, reparse=args.reparse, redownload=args.redownload)
        if args.parse_only:
            return 0

        if store_is_built(settings) and not (args.rebuild or args.reparse):
            _say("Vector store already built; nothing to do. Use --rebuild to re-embed.")
            return 0

        check_ollama(settings)
        if args.limit:
            herbs = herbs[: args.limit]
        docs = herbs_to_documents(herbs)
        _say(f"Embedding {len(docs)} chunks from {len(herbs)} herbs with '{settings.embed_model}'...")

        def progress(done: int, total: int) -> None:
            print(f"\r  {done}/{total}", end="", flush=True)

        build_store(docs, settings, reset=True, on_progress=progress)
        print()
        _say(f"Done. Vector store saved to {settings.chroma_dir.relative_to(settings.root)}/")
        return 0
    except (IngestError, DownloadError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
