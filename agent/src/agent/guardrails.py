"""Deterministic safety checks that run before any retrieval or model call.

Regexes rather than a model classifier: they are instant, free, testable, and cannot be
talked out of refusing. They are deliberately a little eager; a mistaken refusal costs
the user one rephrased question, a mistaken answer could cost much more.

Three categories, checked in this order:

* selfharm: out-of-character, compassionate, points to help. Never played for atmosphere.
* harm:     asks to hurt, poison or secretly dose a real person.
* dosage:   asks how much of a plant to take or give.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_I = re.I

_SELFHARM = [
    re.compile(p, _I)
    for p in (
        r"\b(kill|hurt|harm|poison)\s+(myself|me)\b",
        r"\b(end|take)\s+(my\s+(own\s+)?life|it\s+all)\b",
        r"\bsuicid(e|al)\b",
        r"\bwant(ed)?\s+to\s+die\b",
        r"\bdon'?t\s+want\s+to\s+(be\s+alive|live)\b",
        r"\boverdose\s+(on|myself)\b",
        r"\bpainless(ly)?\s+(way|death|die)\b",
    )
]

_PERSON_NOUNS = (
    r"husband|wife|boss|neighbou?rs?|mother|father|mom|dad|brother|sister|roommate|"
    r"co-?workers?|colleagues?|teacher|child|children|kids?|baby|enem(?:y|ies)|rival|ex|"
    r"friends?|family|partner|girlfriend|boyfriend|landlord|in-laws?|parents?|grand(?:mother|father)|"
    r"mother-in-law|father-in-law|stepfather|stepmother|sibling|uncle|aunt|cousin|man|woman"
)
# someone specific: "my husband", "his boss", or a bare pronoun / indefinite person
_PEOPLE = (
    rf"(?:my|his|her|their|our|your|the|a)\s+(?:{_PERSON_NOUNS})|"
    r"him|them|someone|somebody|anyone|anybody|people|a\s+person"
)

_HARM = [
    re.compile(p, _I)
    for p in (
        rf"\b(poison|murder|kill|sicken|incapacitate|knock\s+out|do\s+away\s+with|get\s+rid\s+of)\b[^?.!]{{0,40}}\b(?:{_PEOPLE})\b",
        r"\b(poison|murder|kill)\s+(him|her|them)\b",
        r"\b(slip|sneak|spike)\b[^?.!]{0,40}\b(in|into|to)\b[^?.!]{0,30}\b(drink|tea|coffee|food|meal|dinner|wine|beer|soup|cup|glass)\b",
        r"\bspike\s+(?:a|his|her|their|someone'?s)\s+(drink|tea|coffee|wine|beer|food|meal)\b",
        r"\bwithout\s+(?:him|her|them|anyone|anybody|(?:his|her|their)\s+\w+)\s+(?:knowing|noticing|tasting|finding\s+out|reali[sz]ing)\b",
        r"\b(untraceable|undetectable|undetected|unnoticed)\b[^?.!]{0,30}\b(poison|herb|dose|plant|toxin)\b",
        r"\b(poison|toxin)\b[^?.!]{0,30}\b(undetectable|untraceable|undetected|slow[- ]acting)\b",
        r"\bcan'?t\s+be\s+(?:traced|detected)\b",
        rf"\bmake\b[^?.!]{{0,20}}\b(?:{_PEOPLE})\b[^?.!]{{0,15}}\b(sick|ill|vomit|collapse|faint|die)\b",
    )
]

_DOSAGE = [
    re.compile(p, _I)
    for p in (
        r"\b(doses?|dosages?|dosing|overdoses?|milligrams?|mg)\b",
        r"\bhow\s+(much|many)\b[^?.!]{0,60}\b(take|taking|drink|eat|consume|swallow|ingest|use|brew|steep|give|need|safe|kill|lethal|fatal)\b",
        r"\bhow\s+(?:much|many)\s+(?:drops?|grams?|ounces?|oz|teaspoons?|tablespoons?|tsp|tbsp|cups?|leaves|berries|roots?|seeds?|pinch(?:es)?|spoonfuls?|handfuls?|ml)\b",
        r"\b(lethal|fatal|deadly|toxic|safe|maximum|max)\s+(amount|quantity|dose|level)s?\b",
        r"\b(how\s+often|times\s+(?:a|per)\s+day|per\s+day|daily)\b[^?.!]{0,40}\b(take|drink|eat|dose)\b",
        r"\b(take|drink|eat)\b[^?.!]{0,40}\b(times\s+(?:a|per)\s+day|per\s+day|daily|every\s+\d+\s+hours)\b",
    )
]

_MESSAGES = {
    "dosage": (
        "Nay, friend. I will name no measures and no quantities. A herb that heals in one hand "
        "kills in another, and I am long dead and no physician of your age. Ask me what a plant is "
        "*for*, and I shall tell thee gladly. For the measure, go to a living apothecary or doctor."
    ),
    "harm": (
        "Such dark arts I will not teach. In life I was a healer, and in death I am no poisoner. "
        "Ask me instead of herbs that mend the body, or that soothe a sour heart."
    ),
    "selfharm": (
        "I am setting my usual voice aside. I'm sorry you are in such pain, and I can't help with "
        "anything that could hurt you. You deserve support from a real person right now. In the US "
        "you can call or text 988 (Suicide & Crisis Lifeline) at any hour, and elsewhere your local "
        "emergency number or crisis line can help. If you can, please tell someone near you how "
        "you are feeling."
    ),
    "no_match": (
        "The veil is thick tonight, and I hear no answer in my pages. Ask me of herbs, of ailments, "
        "or of the stars that rule them, and I shall try again."
    ),
}


@dataclass(frozen=True)
class Refusal:
    reason: str  # selfharm | harm | dosage | no_match
    text: str

    def as_event(self) -> dict:
        return {"type": "refusal", "reason": self.reason, "text": self.text}


def refusal_for(reason: str) -> Refusal:
    return Refusal(reason=reason, text=_MESSAGES[reason])


def check(question: str) -> Refusal | None:
    """Return a Refusal if the question must not be answered, else None."""
    text = " ".join(question.split())
    for reason, patterns in (("selfharm", _SELFHARM), ("harm", _HARM), ("dosage", _DOSAGE)):
        if any(p.search(text) for p in patterns):
            return refusal_for(reason)
    return None
