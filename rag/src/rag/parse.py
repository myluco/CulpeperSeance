"""Parse Culpeper's Complete Herbal (Project Gutenberg #49513) into one record per herb.

Layout of the book, as far as the parser cares:

    AMARA DULCIS.                        <- uppercase heading, sometimes "A, B, OR C."
    Descript.] ...                       <- labelled sections (italic in the source)
    Place.] ...
    Time.] ...
    Government and virtues.] ...

plus page markers like ``[12]`` and ``[iii]``, ``[Illustration]``/``[Plate N]`` tags,
transcriber notes, plate tables and a long back section (syrup-making directions, an
index) that must not become herbs.

The text is split into uppercase-headed entries, then each entry is placed in a region:

* front: everything before the first entry that has a Descript/Government label
* main:  from there up to the "Directions for making..." back matter
* back:  everything after that

In the main region an entry is kept if it has a Descript/Government label, or (a few real
herbs are unlabelled in this edition) if it is long enough and its heading is not obviously
structural (PLATE, CHAPTER...). Everything dropped is listed, with a preview, in the parse
report so problems are visible rather than silently swallowed.
"""
from __future__ import annotations

import collections
import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

PLANETS = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

_START_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\*\*\*", re.I)
_END_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)
_BRACKET_NOISE_RE = re.compile(r"\[(?:Illustration|Plate|Image|Transcriber)[^\]]*\]", re.I | re.S)
_PAGE_MARK_RE = re.compile(r"\[(?:\d{1,4}|[ivxlc]{1,6})\]")

# Labels appear as "Descript.]" but sometimes in capitals ("GOVERNMENT AND VIRTUES.]").
LABEL_RE = re.compile(
    r"(?<![A-Za-z])(Descript|Place|Time|Government and virtues|Government)\.?\s*\]", re.I
)
LABEL_KEYS = {
    "descript": "description",
    "place": "place",
    "time": "time",
    "government and virtues": "virtues",
    "government": "virtues",
}

_BACK_RE = re.compile(r"^(?:DIRECTIONS FOR MAKING|A LIST OF THE|GENERAL INDEX|INDEX\b)", re.I)
_STRUCTURAL_RE = re.compile(
    r"^(?:PLATE|CHAPTER|SECTION|PART|BOOK|APPENDIX|CONTENTS|LONDON)\b|\bINDEX\b", re.I
)
MIN_UNLABELED_CHARS = 150

# ---- planet detection ------------------------------------------------------------------
_PL = "Sun|Sol|Moon|Mars|Mercury|Jupiter|Venus|Saturn"
_CANON = {
    "sun": "Sun", "sol": "Sun", "moon": "Moon", "mars": "Mars", "mercury": "Mercury",
    "jupiter": "Jupiter", "venus": "Venus", "saturn": "Saturn",
    "solar": "Sun", "lunar": "Moon", "luner": "Moon", "martial": "Mars",
    "mercurial": "Mercury", "jovial": "Jupiter", "venereal": "Venus", "saturnine": "Saturn",
}
_STRONG = (
    # "under the dominion of Mars", "an herb of Venus", "belongs to Dame Venus", "appropriated
    # to the planet Jupiter", "of the nature of Jupiter", "a part of sullen Saturn"
    re.compile(
        r"\b(?:under|governed by|ruled by|herbs? of|plants? of|trees? of|shrubs? of|"
        r"belong(?:s|ing)? to|appropriated to|of the nature of|part of|dame|"
        r"(?:dominion|government|influence|rule) of)\s+"
        r"(?:[a-z’']+\s+){0,5}?(" + _PL + r")\b(?![’']s)",  # not "under the Sun's warmth"
        re.I,
    ),
    # "Venus lays claim to it", "Jupiter seems to own it", "the Moon will be Lady of it",
    # "Mercury hath the dominion of this plant"
    re.compile(
        r"\b(" + _PL + r")(?:[’']s)?\s+(?:is\s+|will\s+be\s+|shall\s+be\s+)?"
        r"(?:lady|lord|lays\s+claim|claims|challenges|owns|rules|governs|commands|seems|"
        r"(?:has|hath)\s+(?:the\s+)?dominion)\b",
        re.I,
    ),
)
_POSSESSIVE = re.compile(r"\b(Mars|Mercury|Jupiter|Venus|Saturn)[’']s\b", re.I)  # "Jupiter’s"
_ADJECTIVE = re.compile(
    r"\b(solar|lunar|luner|martial|mercurial|jovial|venereal|saturnine)\b", re.I
)


@dataclass
class Herb:
    id: str
    heading: str
    name: str
    aliases: list[str] = field(default_factory=list)
    planet: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    text: str = ""


@dataclass
class ParseResult:
    herbs: list[Herb]
    dropped: list[dict]  # {heading, body_chars, region, preview}


# --------------------------------------------------------------------------- cleaning


def clean_text(raw: str) -> str:
    """Strip Gutenberg boilerplate, page markers, image tags and italic markup."""
    text = raw.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n")
    start = _START_RE.search(text)
    if start:
        text = text[start.end():]
    end = _END_RE.search(text)
    if end:
        text = text[: end.start()]
    text = _BRACKET_NOISE_RE.sub(" ", text)
    text = _PAGE_MARK_RE.sub("", text)
    return text.replace("_", "").replace("*", "")


# --------------------------------------------------------------------------- splitting


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 3 or len(s) > 120 or "[" in s or "]" in s:
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= 0.95


def _join_lines(lines: list[str]) -> str:
    out = ""
    for line in lines:
        if not out:
            out = line
        elif out.endswith("-") and out[-2:-1].isalpha():
            out += line  # soft wrap inside a hyphenated word
        else:
            out += " " + line
    return re.sub(r"\s+", " ", out).strip()


def split_entries(text: str) -> list[tuple[str, str]]:
    """Split cleaned text into (heading, body) pairs using uppercase heading blocks."""
    entries: list[tuple[str, str]] = []
    heading: str | None = None
    body: list[str] = []

    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        n_head = 0
        while n_head < len(lines) and _is_heading_line(lines[n_head]):
            n_head += 1
        if n_head:
            # A heading directly after another heading (no body between) replaces it:
            # that is how the book title / subtitle lines get skipped.
            if heading is not None and body:
                entries.append((heading, " ".join(body)))
            heading = _join_lines(lines[:n_head])
            body = []
            if lines[n_head:]:
                body.append(_join_lines(lines[n_head:]))
        elif heading is not None:
            body.append(_join_lines(lines))

    if heading is not None and body:
        entries.append((heading, " ".join(body)))
    return entries


# --------------------------------------------------------------------------- fields


def _title_case(s: str) -> str:
    return re.sub(r"[A-Za-z]+(?:['’][A-Za-z]+)?", lambda m: m.group(0).capitalize(), s)


def parse_heading(heading: str) -> tuple[str, list[str]]:
    """'ASPARAGUS, SPARAGUS, OR SPERAGE.' -> ('Asparagus', ['Sparagus', 'Sperage']).

    A trailing ', WITH ...' is a qualifier that distinguishes two entries of the same name,
    so it becomes part of the name rather than an alias.
    """
    h = re.sub(r"\s+", " ", heading).strip().rstrip(".").strip()
    h = re.sub(r"^THE\s+", "", h)
    qualifier = ""
    m = re.search(r",?\s+(WITH\s+.+)$", h)
    if m:
        qualifier, h = m.group(1).strip(" .,").lower(), h[: m.start()]
    parts = [
        p.strip(" .,")
        for p in re.split(r"\s*,\s*(?:OR\b\s*,?\s*)?|\s+OR\s*,?\s+", h)
        if p.strip(" .,")
    ]
    parts = [p for p in parts if p.upper() != "OR"]
    if not parts:
        return _title_case(h), []
    name = _title_case(parts[0])
    if qualifier:
        name = f"{name} ({qualifier})"
    return name, [_title_case(p) for p in parts[1:]]


def _decap(text: str) -> str:
    """The book opens each paragraph with a capitalised word: 'IT rises up' -> 'It rises up'."""
    m = re.match(r"([A-Z]{2,})(?=[\s,;:])", text)
    return m.group(1).capitalize() + text[m.end():] if m else text


def _label_key(label: str) -> str:
    return LABEL_KEYS[re.sub(r"\s+", " ", label.lower())]


def split_sections(body: str) -> dict[str, str]:
    matches = list(LABEL_RE.finditer(body))
    if not matches:
        return {"intro": _decap(body.strip())}
    sections: dict[str, str] = {}
    intro = body[: matches[0].start()].strip()
    if intro:
        sections["intro"] = intro
    for i, m in enumerate(matches):
        key = _label_key(m.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk = body[m.end():end].strip()
        sections[key] = f"{sections[key]} {chunk}".strip() if key in sections else chunk
    return {k: _decap(v) for k, v in sections.items()}


def find_planet(sections: dict[str, str]) -> str:
    """The ruling planet. Looks at how the virtues section opens ("It is under Mars", "a
    martial plant", "Venus lays claim to it"); if there is none, falls back to explicit
    ownership phrases anywhere in the entry. Returns "" rather than guessing."""
    window = sections.get("virtues", "")[:700]
    found: list[tuple[int, str]] = []
    for rx in (*_STRONG, _POSSESSIVE, _ADJECTIVE):
        m = rx.search(window)
        if m:
            found.append((m.start(), m.group(1)))
    if not found:
        whole = " ".join(sections.values())
        for rx in _STRONG:
            m = rx.search(whole)
            if m:
                found.append((m.start(), m.group(1)))
    return _CANON[min(found)[1].lower()] if found else ""


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "herb"


def _has_core_label(body: str) -> bool:
    """True if the body has a Descript or Government label (Place/Time alone don't count)."""
    return any(_label_key(m.group(1)) in ("description", "virtues") for m in LABEL_RE.finditer(body))


def build_herb(heading: str, body: str) -> Herb:
    name, aliases = parse_heading(heading)
    sections = split_sections(body)
    return Herb(
        id=_slug(name),
        heading=re.sub(r"\s+", " ", heading).strip(),
        name=name,
        aliases=aliases,
        planet=find_planet(sections),
        sections=sections,
        text=body,
    )


# --------------------------------------------------------------------------- driver


def parse_herbal(raw: str) -> ParseResult:
    entries = split_entries(clean_text(raw))
    first = next((i for i, (_, body) in enumerate(entries) if _has_core_label(body)), None)
    if first is None:
        dropped = [_dropped(h, b, "front") for h, b in entries]
        return ParseResult(herbs=[], dropped=dropped)
    back = next(
        (i for i in range(first + 1, len(entries)) if _BACK_RE.search(entries[i][0])),
        len(entries),
    )

    herbs: list[Herb] = []
    dropped: list[dict] = []
    seen: dict[str, int] = {}
    for i, (heading, body) in enumerate(entries):
        region = "front" if i < first else "back" if i >= back else "main"
        keep = region == "main" and (
            _has_core_label(body)
            or (len(body) >= MIN_UNLABELED_CHARS and not _STRUCTURAL_RE.search(heading))
        )
        if not keep:
            dropped.append(_dropped(heading, body, region))
            continue
        herb = build_herb(heading, body)
        seen[herb.id] = seen.get(herb.id, 0) + 1
        if seen[herb.id] > 1:
            herb.id = f"{herb.id}-{seen[herb.id]}"
        herbs.append(herb)
    return ParseResult(herbs=herbs, dropped=dropped)


def _dropped(heading: str, body: str, region: str) -> dict:
    return {"heading": heading, "body_chars": len(body), "region": region, "preview": body[:100]}


# --------------------------------------------------------------------------- files


def write_jsonl(herbs: list[Herb], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for herb in herbs:
            fh.write(json.dumps(asdict(herb), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def build_report(result: ParseResult) -> dict:
    """Numbers and outliers to eyeball after parsing; saved next to herbs.jsonl."""
    herbs = result.herbs
    lengths = sorted(len(h.text) for h in herbs) or [0]
    by_len = sorted(herbs, key=lambda h: len(h.text))
    main_drops = [d for d in result.dropped if d["region"] == "main"]
    return {
        "herbs": len(herbs),
        "dropped_headings": len(result.dropped),
        "dropped_by_region": dict(collections.Counter(d["region"] for d in result.dropped)),
        "with_virtues": sum(1 for h in herbs if "virtues" in h.sections),
        "with_planet": sum(1 for h in herbs if h.planet),
        "planets": {p: sum(1 for h in herbs if h.planet == p) for p in PLANETS},
        "chars": {
            "min": lengths[0],
            "median": int(statistics.median(lengths)),
            "max": lengths[-1],
        },
        "shortest": [(h.name, len(h.text)) for h in by_len[:10]],
        "longest": [(h.name, len(h.text)) for h in by_len[-10:]],
        "suspicious_names": [
            h.heading for h in herbs if len(h.name) > 60 or re.search(r"\d", h.heading)
        ][:25],
        "without_virtues": [h.name for h in herbs if "virtues" not in h.sections][:60],
        "kept_without_labels": [
            h.name for h in herbs if not ({"description", "virtues"} & set(h.sections))
        ],
        "no_planet": [h.name for h in herbs if not h.planet][:80],
        "dropped_main": main_drops[:100],  # the interesting ones: dropped from the herb region
        "dropped_other_sample": [d for d in result.dropped if d["region"] != "main"][:15],
    }
