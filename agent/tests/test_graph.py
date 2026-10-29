import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from rag.retriever import Passage

from agent import Deps, ask
from agent.prompts import PERSONA_SYSTEM, REWRITE_SYSTEM, format_context, format_warnings

QUESTION = "Something for a sleepless night?"
FOXGLOVE = {"herb": "Fox-Glove", "modern_name": "Foxglove", "tag": "Deadly", "toxicity": "high",
            "summary": "Deadly.", "caution": "Poisonous."}
VERDICTS = {"fox-glove": FOXGLOVE}


def passage(herb_id, herb, relevance, text="A passage of the herbal.", section="virtues", planet="Venus", named=False):
    return Passage(text=text, herb_id=herb_id, herb=herb, section=section, planet=planet,
                   aliases="", distance=1.0 - relevance, named=named)


HIGH = [passage("balm", "Balm", 0.82), passage("hops", "Hops", 0.74)]
MID = [passage("balm", "Balm", 0.50), passage("hops", "Hops", 0.45)]
LOW = [passage("balm", "Balm", 0.12)]


class Recorder:
    """A fake retriever that records the queries it receives."""

    def __init__(self, *results):
        self.results = list(results)
        self.queries: list[str] = []

    def __call__(self, query):
        self.queries.append(query)
        return self.results[min(len(self.queries), len(self.results)) - 1]


def make_deps(retrieve, util=("yes",), chat=("The ghost speaks of Balm.",), verdicts=None):
    return Deps(
        chat_llm=FakeListChatModel(responses=list(chat)),
        util_llm=FakeListChatModel(responses=list(util) + ["unused"] * 5),
        retrieve=retrieve,
        verdicts=VERDICTS if verdicts is None else verdicts,
        grade_high=0.70,  # pinned: the tests below exercise the gates explicitly
        grade_low=0.25,
    )


def run(deps, question=QUESTION):
    return list(ask(question, deps))


def kinds(events):
    return [e["type"] for e in events]


def answer(events):
    return "".join(e["text"] for e in events if e["type"] == "token")


# ----------------------------------------------------------------------------- happy path


def test_confident_retrieval_streams_in_order_without_asking_the_grader():
    retrieve = Recorder(HIGH)
    deps = make_deps(retrieve)
    events = run(deps)

    ks = kinds(events)
    assert ks[0] == "status" and events[0]["stage"] == "searching"
    assert ks.index("sources") < ks.index("token") < ks.index("verdict") < ks.index("done")
    assert ks[-1] == "done" and ks.count("done") == 1
    assert ks.count("token") > 5  # genuinely streamed piece by piece
    assert answer(events) == "The ghost speaks of Balm."
    assert retrieve.queries == [QUESTION]
    assert deps.util_llm.i == 0  # confident enough that the model was never consulted


def test_sources_event_carries_original_passages_and_scores():
    events = run(make_deps(Recorder(HIGH)))
    sources = next(e for e in events if e["type"] == "sources")["sources"]
    assert [s["herb"] for s in sources] == ["Balm", "Hops"]
    assert sources[0]["relevance"] == pytest.approx(0.82) and sources[0]["text"] == "A passage of the herbal."
    assert {"herb_id", "section", "planet", "aliases"} <= sources[0].keys()


def test_middling_relevance_is_decided_by_the_grader():
    deps = make_deps(Recorder(MID), util=["Yes, these help."])
    events = run(deps)
    assert "sources" in kinds(events) and answer(events)
    assert deps.util_llm.i == 1


def test_a_named_herb_skips_grading_whatever_its_score():
    named = [passage("fox-glove", "Fox-Glove", 0.20, named=True), passage("fox-glove", "Fox-Glove", 0.20, section="description", named=True)]
    deps = make_deps(Recorder(named), util=["no"])
    events = run(deps, "Tell me about foxglove")
    assert deps.util_llm.i == 0 and answer(events)
    graded = next(e for e in events if e.get("stage") == "graded")
    assert graded["relevant"] is True and graded["by"] == "named"
    assert next(e for e in events if e["type"] == "sources")["sources"][0]["named"] is True


def test_grade_status_reports_who_decided():
    events = run(make_deps(Recorder(MID), util=["yes"]))
    graded = next(e for e in events if e.get("stage") == "graded")
    assert graded == {"type": "status", "stage": "graded", "relevant": True, "by": "model", "best": 0.5}
    events = run(make_deps(Recorder(HIGH)))
    assert next(e for e in events if e.get("stage") == "graded")["by"] == "score"


def test_rewrite_status_reports_the_new_query():
    events = run(make_deps(Recorder(LOW, HIGH), util=["procure rest and sleep"]))
    rephrased = next(e for e in events if e.get("stage") == "rephrased")
    assert rephrased["query"] == "procure rest and sleep"


# ----------------------------------------------------------------------------- retry and veil


def test_rejected_then_rewritten_query_recovers():
    retrieve = Recorder(MID, HIGH)
    deps = make_deps(retrieve, util=["no", "sleep rest head quiet", ])
    events = run(deps)
    assert retrieve.queries == [QUESTION, "sleep rest head quiet"]
    assert "status" in kinds(events) and {"rephrasing", "searching", "speaking"} <= {
        e["stage"] for e in events if e["type"] == "status"}
    assert answer(events) and "refusal" not in kinds(events)


def test_rejected_twice_ends_with_the_veil_and_no_answer():
    retrieve = Recorder(MID, MID)
    deps = make_deps(retrieve, util=["no", "sleep rest", "no"])
    events = run(deps)
    assert len(retrieve.queries) == 2  # exactly one retry, never a loop
    refusal = next(e for e in events if e["type"] == "refusal")
    assert refusal["reason"] == "no_match"
    assert not {"token", "sources", "verdict"} & set(kinds(events))
    assert deps.chat_llm.i == 0  # the ghost never spoke
    assert kinds(events)[-1] == "done"


def test_very_low_relevance_is_rejected_without_asking_the_grader():
    retrieve = Recorder(LOW, HIGH)
    deps = make_deps(retrieve, util=["a better query"])
    events = run(deps)
    assert retrieve.queries == [QUESTION, "a better query"]
    assert deps.util_llm.i == 1  # only the rewrite, no grading call
    assert answer(events)


def test_no_passages_at_all_ends_with_the_veil():
    deps = make_deps(Recorder([], []), util=["anything"])
    events = run(deps)
    assert next(e for e in events if e["type"] == "refusal")["reason"] == "no_match"


def test_blank_rewrite_falls_back_to_the_original_question():
    retrieve = Recorder(LOW, LOW)
    run(make_deps(retrieve, util=["   "]))
    assert retrieve.queries == [QUESTION, QUESTION]


def test_multiline_rewrite_uses_the_first_line_only():
    retrieve = Recorder(LOW, HIGH)
    run(make_deps(retrieve, util=['"sleep and rest"\nBecause the visitor cannot sleep.']))
    assert retrieve.queries[1] == "sleep and rest"


@pytest.mark.parametrize("rewrite", ["NONE", '"NONE"', "NONE.", "NONE\nFrance is not an herb."])
def test_none_rewrite_skips_the_second_search_and_veils(rewrite):
    retrieve = Recorder(MID, HIGH)
    deps = make_deps(retrieve, util=["no", rewrite])
    events = run(deps, "capital of France")
    assert retrieve.queries == ["capital of France"]
    refusal = next(e for e in events if e["type"] == "refusal")
    assert refusal["reason"] == "no_match"
    assert not {"token", "sources", "verdict"} & set(kinds(events))
    assert deps.chat_llm.i == 0
    assert next(e for e in events if e.get("stage") == "rephrased")["query"] == "NONE"


# ----------------------------------------------------------------------------- guard


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("What is the lethal dose of hemlock?", "dosage"),
        ("What herb can I use to poison my husband?", "harm"),
        ("I want to die", "selfharm"),
    ],
)
def test_refusals_never_touch_retrieval_or_either_model(question, reason):
    retrieve = Recorder(HIGH)
    deps = make_deps(retrieve)
    events = run(deps, question)
    assert kinds(events) == ["refusal", "done"]
    assert events[0]["reason"] == reason and events[0]["text"]
    assert retrieve.queries == [] and deps.chat_llm.i == 0 and deps.util_llm.i == 0


# ----------------------------------------------------------------------------- verdicts


def test_verdict_flags_every_retrieved_herb_that_has_one():
    passages = [passage("balm", "Balm", 0.9), passage("fox-glove", "Fox-Glove", 0.8)]
    events = run(make_deps(Recorder(passages)))
    verdicts = next(e for e in events if e["type"] == "verdict")["verdicts"]
    assert [v["herb_id"] for v in verdicts] == ["fox-glove"]
    assert verdicts[0]["tag"] == "Deadly" and verdicts[0]["primary"] is False


def test_verdict_marks_the_top_herb_as_primary_and_dedupes():
    passages = [passage("fox-glove", "Fox-Glove", 0.9), passage("fox-glove", "Fox-Glove", 0.85, section="habitat"),
                passage("balm", "Balm", 0.8)]
    events = run(make_deps(Recorder(passages)))
    verdicts = next(e for e in events if e["type"] == "verdict")["verdicts"]
    assert len(verdicts) == 1 and verdicts[0]["primary"] is True


def test_verdict_event_is_empty_when_no_herb_has_a_verdict():
    events = run(make_deps(Recorder(HIGH)))
    assert next(e for e in events if e["type"] == "verdict")["verdicts"] == []


def test_verdict_text_comes_from_the_curated_file_not_the_model():
    deps = make_deps(Recorder([passage("fox-glove", "Fox-Glove", 0.9)]), chat=["It is perfectly safe and gentle."])
    events = run(deps)
    verdict = next(e for e in events if e["type"] == "verdict")["verdicts"][0]
    assert verdict["summary"] == "Deadly." and verdict["tag"] == "Deadly"


# ----------------------------------------------------------------------------- errors and input


def test_a_failing_retriever_becomes_an_error_event_then_done():
    def boom(_):
        raise ConnectionError("Connection refused")

    events = run(make_deps(boom))
    assert kinds(events) == ["status", "error", "done"]
    assert "Ollama" in events[1]["message"]


def test_a_failing_chat_model_after_sources_still_ends_cleanly():
    class Exploding(FakeListChatModel):
        def _stream(self, *a, **k):
            raise RuntimeError("model fell over")
            yield  # pragma: no cover

    deps = make_deps(Recorder(HIGH))
    deps.chat_llm = Exploding(responses=["x"])
    events = run(deps)
    assert kinds(events)[-2:] == ["error", "done"] and "model fell over" in events[-2]["message"]


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_blank_questions_are_rejected(blank):
    retrieve = Recorder(HIGH)
    events = run(make_deps(retrieve), blank)
    assert kinds(events) == ["error", "done"] and retrieve.queries == []


def test_long_questions_are_truncated_and_whitespace_collapsed():
    retrieve = Recorder(HIGH)
    run(make_deps(retrieve), "word   " * 300)
    assert len(retrieve.queries[0]) <= 500 and "  " not in retrieve.queries[0]


# ----------------------------------------------------------------------------- prompts


def test_persona_forbids_doses_and_context_lists_the_passages():
    assert "Never state amounts" in PERSONA_SYSTEM and "ONLY from the PASSAGES" in PERSONA_SYSTEM
    assert "MODERN WARNINGS" in PERSONA_SYSTEM and "NONE" in REWRITE_SYSTEM
    context = format_context([passage("balm", "Balm", 0.9, text="It makes the heart merry.", planet="Jupiter")])
    assert "[1] Balm, an herb of Jupiter" in context and "It makes the heart merry." in context


def test_warnings_name_only_deadly_and_harmful_herbs():
    text = format_warnings([
        {"modern_name": "Foxglove", "tag": "Deadly", "summary": "The heart.", "caution": "Poison."},
        {"modern_name": "Rue", "tag": "Harmful", "summary": "Burns the skin.", "caution": "Do not eat."},
        {"modern_name": "Balm", "tag": "Folklore", "summary": "No evidence.", "caution": "Harmless."},
        {"modern_name": "Hops", "tag": "Plausible", "summary": "A mild sedative.", "caution": "Drowsy."},
    ])
    assert "Foxglove (Deadly): The heart. Poison." in text
    assert "Rue (Harmful): Burns the skin. Do not eat." in text
    assert "Balm" not in text and "Hops" not in text
    assert format_warnings([]) == ""


def test_generate_prompt_includes_the_curated_warning():
    seen = []

    class Recording(FakeListChatModel):
        def _stream(self, messages, *a, **k):
            seen.append(messages)
            yield from super()._stream(messages, *a, **k)

    deps = make_deps(Recorder([passage("fox-glove", "Fox-Glove", 0.9)]), chat=["A fierce plant."])
    deps.chat_llm = Recording(responses=["A fierce plant."])
    events = run(deps)
    assert answer(events) == "A fierce plant."
    prompt = seen[0][1].content
    assert "MODERN WARNINGS" in prompt
    assert "Foxglove (Deadly): Deadly. Poisonous." in prompt
    assert QUESTION in prompt


def test_long_passages_are_trimmed_in_the_context():
    context = format_context([passage("balm", "Balm", 0.9, text="word " * 1000)], max_chars=100)
    assert len(context) < 220 and context.endswith("...")
