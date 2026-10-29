# The Culpeper Séance

Summon the ghost of Nicholas Culpeper (1616–1654) and ask him for herbal remedies. He answers in
character, grounded in the actual text of *The Complete Herbal*, and a "Beyond the Veil" panel
reports what modern science says (usually: please don't drink that).

Built for the **Ghost in the Machine** challenge with open pieces only: an open-weight model
served by Ollama, LangChain + LangGraph, Chroma, and a public-domain book.

## Layout

```
ui/       React + Vite + TypeScript front end            (own package.json)
server/   Flask API, SSE streaming                       (own pyproject.toml)
agent/    LangGraph agent: guard -> retrieve -> grade -> generate -> verdict
rag/      download, parse, chunk, embed, persist, retrieve (+ one-time ingest CLI)
data/     artifacts only, never code
  raw/        downloaded Gutenberg text (git-ignored)
  processed/  herbs.jsonl (canonical parsed herbs) + parse_report.json
  chroma/     persisted vector DB (git-ignored)
  verdicts.json  hand-curated modern verdicts (toxicity claims are never model-generated)
```

Dependencies flow one way: `server -> agent -> rag`. Each package has its own manifest; the root
holds only the `Makefile`, this file and `.env.example`.

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/), Node 20+, [Ollama](https://ollama.com)
- A chat model, e.g. `gemma3:31b-cloud` (`ollama signin` for cloud-tagged models)
- An embedding model, pulled locally: `ollama pull nomic-embed-text`

## Commands

```bash
cp .env.example .env     # adjust model names if needed
make setup               # venv + install rag/agent/server + npm install   (PYTHON=3.13 to pin)
make ingest              # ONE TIME: download, parse, chunk, embed, persist to data/chroma
make dev                 # Flask API + Vite UI together
make test                # Python tests
```

`make ingest` is safe to re-run: it does nothing if the store exists. `make ingest-rebuild`
re-embeds from `data/processed/herbs.jsonl` without re-parsing (use after changing `EMBED_MODEL`
or chunk size). The server only ever *opens* the persisted store; it never embeds the book.

Useful flags: `python -m rag.ingest --parse-only` (parse + report, no Ollama needed),
`--reparse`, `--limit 20` (embed 20 herbs as a smoke test).

## Status

| Piece | State |
|---|---|
| rag: download, parse, chunk, Chroma store, retriever, ingest CLI | built, 26 tests passing |
| Parser validated against the real Gutenberg text | pending (see `data/processed/parse_report.json` after first ingest) |
| agent (LangGraph), verdicts.json | built |
| server (Flask + SSE): POST /api/ask, GET /api/herbs, GET /api/health | built |
| ui (React/Vite): séance, grimoire, verdict stamps, poison cabinet | built |
