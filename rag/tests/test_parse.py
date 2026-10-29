from pathlib import Path

import pytest

from rag.parse import (
    LABEL_RE,
    build_herb,
    build_report,
    clean_text,
    find_planet,
    parse_heading,
    parse_herbal,
    read_jsonl,
    split_sections,
    write_jsonl,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_herbal.txt"


def parsed():
    return parse_herbal(FIXTURE.read_text(encoding="utf-8"))


def by_name(result):
    return {h.name: h for h in result.herbs}


def entry(name: str, body: str = "_Descript._] Real entry.") -> str:
    return f"{name}.\n\n{body}\n\n"


# ------------------------------------------------------------------ the fixture book


def test_finds_only_real_herbs():
    assert [h.name for h in parsed().herbs] == ["Alehoof", "Asparagus", "Balm", "Water Betony"]


def test_front_matter_plates_and_license_are_not_herbs():
    result = parsed()
    headings = " ".join(h.heading for h in result.herbs)
    for noise in ("PLATE", "THOMAS KELLY", "ENGLISH PHYSICIAN", "LICENSE", "NEVER BECOME"):
        assert noise not in headings
        assert noise not in " ".join(h.text for h in result.herbs)


def test_aliases_and_wrapped_headings():
    herbs = by_name(parsed())
    assert herbs["Alehoof"].aliases == ["Ground-Ivy"]
    assert herbs["Asparagus"].aliases == ["Sparagus", "Sperage"]
    assert herbs["Asparagus"].heading == "ASPARAGUS, SPARAGUS, OR SPERAGE."


def test_sections_are_split_and_page_markers_removed():
    herbs = by_name(parsed())
    alehoof = herbs["Alehoof"]
    assert set(alehoof.sections) == {"description", "place", "time", "virtues"}
    assert "take root wherever" in alehoof.sections["description"]  # "[2]" removed
    assert "[" not in alehoof.text  # no page markers; only the "Label.]" closers remain
    assert "_" not in alehoof.text
    assert herbs["Balm"].sections.keys() == {"description", "virtues"}


def test_section_text_does_not_leak_between_sections():
    alehoof = by_name(parsed())["Alehoof"]
    assert "April" in alehoof.sections["time"]
    assert "April" not in alehoof.sections["virtues"]
    assert "hedges" in alehoof.sections["place"]


def test_planets():
    herbs = by_name(parsed())
    assert herbs["Alehoof"].planet == "Venus"
    assert herbs["Asparagus"].planet == "Moon"
    assert herbs["Balm"].planet == "Jupiter"
    assert herbs["Water Betony"].planet == "Jupiter"


def test_ids_are_unique_slugs():
    assert [h.id for h in parsed().herbs] == ["alehoof", "asparagus", "balm", "water-betony"]


def test_jsonl_roundtrip_and_report(tmp_path):
    result = parsed()
    path = tmp_path / "out" / "herbs.jsonl"
    write_jsonl(result.herbs, path)
    rows = read_jsonl(path)
    assert [r["id"] for r in rows] == [h.id for h in result.herbs]
    assert rows[0]["sections"]["virtues"].startswith("It is under the dominion of Venus")
    report = build_report(result)
    assert report["herbs"] == 4 and report["with_planet"] == 4 and report["planets"]["Jupiter"] == 2
    assert report["without_virtues"] == [] and report["kept_without_labels"] == []


# ------------------------------------------------------------------ regions and dropping


def test_duplicate_names_get_suffixes():
    raw = "".join(entry("BALM", f"_Descript._] Entry number {i}.") for i in range(3))
    assert [h.id for h in parse_herbal(raw).herbs] == ["balm", "balm-2", "balm-3"]


def test_front_matter_before_first_labelled_entry_is_dropped_and_reported():
    prose = "Just some prose with no labelled sections at all."
    raw = entry("ODD HEADING", prose) + entry("BALM")
    result = parse_herbal(raw)
    assert [h.name for h in result.herbs] == ["Balm"]
    assert result.dropped == [
        {"heading": "ODD HEADING.", "body_chars": len(prose), "region": "front", "preview": prose}
    ]


def test_long_unlabelled_entry_in_main_text_is_kept():
    prose = "Unlabelled prose about the herb. " * 10
    raw = entry("BALM") + entry("CAMOMILE", prose) + entry("WATER BETONY")
    result = parse_herbal(raw)
    assert [h.name for h in result.herbs] == ["Balm", "Camomile", "Water Betony"]
    camomile = by_name(result)["Camomile"]
    assert set(camomile.sections) == {"intro"}
    assert build_report(result)["kept_without_labels"] == ["Camomile"]


def test_short_or_structural_unlabelled_entries_in_main_text_are_dropped():
    long_prose = "Plenty of prose that goes on and on. " * 10
    raw = (
        entry("BALM")
        + entry("TOO SHORT", "Only a few words.")
        + entry("CHAPTER III", long_prose)
        + entry("PLATE 7", long_prose)
        + entry("WATER BETONY")
    )
    result = parse_herbal(raw)
    assert [h.name for h in result.herbs] == ["Balm", "Water Betony"]
    assert {d["heading"]: d["region"] for d in result.dropped} == {
        "TOO SHORT.": "main",
        "CHAPTER III.": "main",
        "PLATE 7.": "main",
    }
    assert build_report(result)["dropped_by_region"] == {"main": 3}


def test_back_matter_is_cut_off():
    prose = "Boil it well and keep it in a pot. " * 12
    raw = (
        entry("BALM")
        + entry("DIRECTIONS FOR MAKING SYRUPS, CONSERVES,", prose)
        + entry("SOME HERB", "_Descript._] Must be ignored in the back matter.")
        + entry("A LIST OF THE PRINCIPAL DISEASES", "Abortion. Sage, 244. Place.] Time.]")
    )
    result = parse_herbal(raw)
    assert [h.name for h in result.herbs] == ["Balm"]
    assert {d["region"] for d in result.dropped} == {"back"}
    assert len(result.dropped) == 3


def test_text_without_any_labels_yields_nothing():
    result = parse_herbal(entry("PLATE I", "A table of plants.") + entry("PREFACE", "Words."))
    assert result.herbs == []
    assert {d["region"] for d in result.dropped} == {"front"}


def test_heading_and_body_in_same_block():
    raw = "BALM.\n_Descript._] Body follows immediately.\n_Place._] Gardens.\n"
    herbs = parse_herbal(raw).herbs
    assert herbs[0].sections["description"] == "Body follows immediately."
    assert herbs[0].sections["place"] == "Gardens."


# ------------------------------------------------------------------ headings and names


def test_parse_heading_variants():
    assert parse_heading("THE BLACK ALDER-TREE.") == ("Black Alder-Tree", [])
    assert parse_heading("LADY'S MANTLE.") == ("Lady's Mantle", [])
    assert parse_heading("ALEHOOF, OR GROUND-IVY.") == ("Alehoof", ["Ground-Ivy"])
    assert parse_heading("MARSH-MALLOWS OR MALLOW") == ("Marsh-Mallows", ["Mallow"])


def test_curly_apostrophes_are_title_cased_correctly():
    assert parse_heading("ADDER’S TONGUE, OR SERPENT’S TONGUE.") == ("Adder’s Tongue", ["Serpent’s Tongue"])
    assert parse_heading("ST. JOHN’S WORT.") == ("St. John’s Wort", [])
    assert parse_heading("LADIES’ MANTLE.") == ("Ladies’ Mantle", [])


def test_stray_or_separators_do_not_become_aliases():
    assert parse_heading("THE WOOLLEN, OR, COTTON THISTLE.") == ("Woollen", ["Cotton Thistle"])
    assert parse_heading("WALL RUE, OR, WHITE MAIDEN-HAIR.") == ("Wall Rue", ["White Maiden-Hair"])
    assert parse_heading("WOLD, WELD, OR DYER’S WEED.") == ("Wold", ["Weld", "Dyer’s Weed"])


def test_with_qualifier_distinguishes_same_named_entries():
    assert parse_heading("LOOSESTRIFE, WITH SPIKED HEADS OF FLOWERS.") == (
        "Loosestrife (with spiked heads of flowers)",
        [],
    )
    raw = entry("LOOSESTRIFE OR WILLOW-HERB") + entry("LOOSESTRIFE, WITH SPIKED HEADS OF FLOWERS")
    assert [h.id for h in parse_herbal(raw).herbs] == [
        "loosestrife",
        "loosestrife-with-spiked-heads-of-flowers",
    ]


# ------------------------------------------------------------------ labels and sections


def test_label_regex_variants():
    for label in (
        "Descript.]", "Descript]", "Government and virtues.]", "Government and Virtues.]",
        "GOVERNMENT AND VIRTUES.]", "Time. ]",
    ):
        assert LABEL_RE.search(f"text {label} more"), label
    assert not LABEL_RE.search("it was the Time of the year")
    assert not LABEL_RE.search("a Place in the garden")


def test_uppercase_label_is_recognised_as_virtues():
    herb = build_herb("LILY", "Descript.] Roots. GOVERNMENT AND VIRTUES.] It is under the dominion of Mercury.")
    assert herb.sections["virtues"] == "It is under the dominion of Mercury."
    assert herb.planet == "Mercury"


def test_split_sections_keeps_intro():
    sections = split_sections("Preamble words. Descript.] Body. Place.] Here.")
    assert sections == {"intro": "Preamble words.", "description": "Body.", "place": "Here."}


def test_drop_cap_words_are_normalised():
    sections = split_sections("CALLED also Conval Lily. Descript.] IT rises up. Place.] I found it. Time.] OUR hedges.")
    assert sections == {
        "intro": "Called also Conval Lily.",
        "description": "It rises up.",
        "place": "I found it.",
        "time": "Our hedges.",
    }
    assert split_sections("THIS herb is unlabelled.") == {"intro": "This herb is unlabelled."}
    assert split_sections("Descript.] ST. John’s wort.")["description"] == "ST. John’s wort."


# ------------------------------------------------------------------ planets


@pytest.mark.parametrize(
    ("virtues", "planet"),
    [
        ("It is under the dominion of Mars.", "Mars"),
        ("It is under the planet Mercury, and a notable herb of his.", "Mercury"),
        ("This is a herb of Saturn.", "Saturn"),
        ("It is under Mercury.", "Mercury"),
        ("Governed by the Sun.", "Sun"),
        ("The herb belongs to Saturn, yet is very harmless.", "Saturn"),
        ("These also belong to Dame Venus, and strengthen the kidneys.", "Venus"),
        ("The herb is appropriated to the planet Jupiter, and the sign Aries.", "Jupiter"),
        ("These are of the nature of Jupiter, and under his dominion.", "Jupiter"),
        ("Venus lays claim to this herb as her own.", "Venus"),
        ("Venus is Lady of it.", "Venus"),
        ("Jupiter seems to own this herb.", "Jupiter"),
        ("Saturn seems to me to own the herb, and yet some hold the Sun.", "Saturn"),
        ("Cancer claims the herb, and the Moon will be Lady of it.", "Moon"),
        ("It is under the sign of the Lion, and Sol claims dominion over it.", "Sun"),
        ("It is under the celestial sign Leo, and the dominion of the Sun.", "Sun"),
        ("Mercury hath the dominion of this plant.", "Mercury"),
        ("Now Dame Venus hath fitted women with two herbs of one name.", "Venus"),
        ("The herb is Jupiter’s, and the sign Cancer.", "Jupiter"),
        ("The fruit is old Saturn’s, and sure a better medicine he hardly hath.", "Saturn"),
        ("It is a malicious part of sullen Saturn.", "Saturn"),
        ("They are furious martial plants.", "Mars"),
        ("This is also a Mercurial plant.", "Mercury"),
        ("It is a cold and saturnine plant.", "Saturn"),
        ("It is a fine cooling, cleansing, jovial plant.", "Jupiter"),
        ("The plant is venereal, and breeds seed exceedingly.", "Venus"),
        ("This admirable solar shrub is scarce to be paralleled.", "Sun"),
        ("It is a Lunar herb.", "Moon"),
        ("The herb is Luner.", "Moon"),
        ("Mercury, they say, owns the herb, but I rather think it is Venus’s.", "Venus"),
        ("A plain herb with no ruler.", ""),
        ("It is good against the heat of the sun and the cold of the moon.", ""),
    ],
)
def test_find_planet(virtues, planet):
    assert find_planet({"virtues": virtues}) == planet


def test_find_planet_falls_back_to_strong_phrases_elsewhere_in_the_entry():
    assert find_planet({"description": "Rough leaves.", "place": "It is a plant of Saturn."}) == "Saturn"
    assert find_planet({"description": "It grew under the Sun's warmth."}) == ""


# ------------------------------------------------------------------ cleaning


def test_clean_text_strips_noise():
    out = clean_text(
        "*** START OF THE PROJECT GUTENBERG EBOOK X ***\nbetided[2] them [iii] [Illustration: a\nplant] "
        "_Descript._]\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nlicense"
    )
    assert "betided them" in out
    assert "[" not in out.replace("]", "") and "Illustration" not in out
    assert "license" not in out and "START" not in out
