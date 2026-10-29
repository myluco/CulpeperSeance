"""Graph nodes. Each factory closes over `Deps` and returns a plain function of the state.

Nodes talk to the outside world through LangGraph's custom stream writer, emitting small
typed events (status, sources, token, verdict, refusal). The server turns those straight
into server-sent events, so nothing downstream has to know about LangGraph.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from . import guardrails, prompts
from .deps import Deps
from .state import AgentState
from .verdicts import verdicts_for


def _text(chunk) -> str:
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # content blocks
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return ""


def make_guard():
    def guard(state: AgentState) -> dict:
        refusal = guardrails.check(state["question"])
        return {"refusal": {"reason": refusal.reason, "text": refusal.text}} if refusal else {}

    return guard


def make_retrieve(deps: Deps):
    def retrieve(state: AgentState) -> dict:
        get_stream_writer()({"type": "status", "stage": "searching"})
        query = state.get("rewritten_query") or state["question"]
        return {"passages": deps.retrieve(query)}

    return retrieve


def make_grade(deps: Deps):
    def grade(state: AgentState) -> dict:
        write = get_stream_writer()
        passages = state.get("passages") or []
        best = max((p.relevance for p in passages), default=0.0)

        def done(relevant: bool, by: str) -> dict:
            write({"type": "status", "stage": "graded", "relevant": relevant, "by": by, "best": round(best, 3)})
            return {"relevant": relevant}

        if not passages:
            return done(False, "empty")
        if any(p.named for p in passages):
            return done(True, "named")  # the visitor named the herb: nothing to judge
        if best >= deps.grade_high:
            return done(True, "score")
        if best < deps.grade_low:
            return done(False, "score")
        messages = [
            SystemMessage(prompts.GRADE_SYSTEM),
            HumanMessage(
                prompts.GRADE_USER.format(
                    question=state["question"], context=prompts.format_snippets(passages)
                )
            ),
        ]
        verdict = _text(deps.util_llm.invoke(messages)).strip().lower()
        return done(verdict.startswith("yes"), "model")

    return grade


def _rewrite_line(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[0].strip("\"'` ") if lines else ""


def _is_off_topic(query: str) -> bool:
    return query.rstrip(".").upper() == "NONE"


def make_rewrite(deps: Deps):
    def rewrite(state: AgentState) -> dict:
        write = get_stream_writer()
        write({"type": "status", "stage": "rephrasing"})
        messages = [
            SystemMessage(prompts.REWRITE_SYSTEM),
            HumanMessage(prompts.REWRITE_USER.format(question=state["question"])),
        ]
        query = _rewrite_line(_text(deps.util_llm.invoke(messages)))
        attempts = state.get("attempts", 0) + 1
        if _is_off_topic(query):
            write({"type": "status", "stage": "rephrased", "query": "NONE"})
            return {"off_topic": True, "attempts": attempts}
        query = query or state["question"]
        write({"type": "status", "stage": "rephrased", "query": query})
        return {"off_topic": False, "rewritten_query": query, "attempts": attempts}

    return rewrite


def make_generate(deps: Deps):
    def generate(state: AgentState) -> dict:
        write = get_stream_writer()
        passages = state["passages"]
        write(
            {
                "type": "sources",
                "sources": [
                    {
                        "herb_id": p.herb_id,
                        "herb": p.herb,
                        "section": p.section,
                        "planet": p.planet,
                        "aliases": p.aliases,
                        "text": p.text,
                        "relevance": round(p.relevance, 3),
                        "named": p.named,
                    }
                    for p in passages
                ],
            }
        )
        write({"type": "status", "stage": "speaking"})
        warnings = prompts.format_warnings(verdicts_for(passages, deps.verdicts))
        messages = [
            SystemMessage(prompts.PERSONA_SYSTEM),
            HumanMessage(
                prompts.PERSONA_USER.format(
                    context=prompts.format_context(passages),
                    warnings=warnings,
                    question=state["question"],
                )
            ),
        ]
        parts: list[str] = []
        for chunk in deps.chat_llm.stream(messages):
            piece = _text(chunk)
            if piece:
                parts.append(piece)
                write({"type": "token", "text": piece})
        return {"answer": "".join(parts)}

    return generate


def make_verdict(deps: Deps):
    def verdict(state: AgentState) -> dict:
        found = verdicts_for(state.get("passages") or [], deps.verdicts)
        get_stream_writer()({"type": "verdict", "verdicts": found})
        return {"verdicts": found}

    return verdict


def refuse(state: AgentState) -> dict:
    get_stream_writer()({"type": "refusal", **state["refusal"]})
    return {}


def veil(state: AgentState) -> dict:
    refusal = guardrails.refusal_for("no_match")
    get_stream_writer()(refusal.as_event())
    return {"refusal": {"reason": refusal.reason, "text": refusal.text}}
