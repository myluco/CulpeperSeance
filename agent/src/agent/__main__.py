"""Command-line seance, and a probe for calibrating the relevance thresholds.

    python -m agent "Something for a sleepless night?"
    python -m agent --probe "Something for a sleepless night?" "capital of France"
"""
from __future__ import annotations

import argparse
import sys

from rag.retriever import retrieve


def probe(questions: list[str]) -> None:
    from .deps import default_deps

    deps = default_deps()
    print(f"grade_low={deps.grade_low}  grade_high={deps.grade_high}  (relevance = 1 - cosine distance)")
    for q in questions:
        print(f"\n{q}")
        for p in deps.retrieve(q):
            print(f"  {p.relevance:.3f}  {p.herb} ({p.section}){'  [named]' if p.named else ''}")


def seance(question: str) -> None:
    from .run import ask

    for event in ask(question):
        kind = event["type"]
        if kind == "token":
            print(event["text"], end="", flush=True)
        elif kind == "status":
            extra = {k: v for k, v in event.items() if k not in ("type", "stage")}
            print(f"[{event['stage']}]" + (f" {extra}" if extra else ""), file=sys.stderr, flush=True)
        elif kind == "sources":
            print("\nSources: " + ", ".join(f"{s['herb']}/{s['section']} ({s['relevance']}{', named' if s.get('named') else ''})" for s in event["sources"]), file=sys.stderr)
        elif kind == "verdict":
            for v in event["verdicts"]:
                print(f"\n[{v['tag'].upper()} / {v['toxicity']}] {v['modern_name']}: {v['summary']}")
        elif kind in ("refusal", "error"):
            print(event.get("text") or event["message"])
    print()


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent", description=__doc__.split("\n")[0])
    parser.add_argument("questions", nargs="+")
    parser.add_argument("--probe", action="store_true", help="print retrieval scores instead of answering")
    args = parser.parse_args()
    if args.probe:
        probe(args.questions)
    else:
        seance(" ".join(args.questions))


if __name__ == "__main__":
    main()
