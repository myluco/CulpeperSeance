"""The LangGraph: guard -> retrieve -> grade -> (rewrite -> retrieve ->) generate -> verdict.

        START -> guard --refusal--> refuse -> END
                   |
                retrieve <---------- rewrite_query --NONE--> veil -> END
                   |                     ^
                 grade --not relevant, 1st time
                   |  \\
                   |   --not relevant, 2nd time--> veil -> END
                generate -> verdict -> END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .deps import Deps
from .state import AgentState

MAX_REWRITES = 1


def route_after_guard(state: AgentState) -> str:
    return "refuse" if state.get("refusal") else "retrieve"


def route_after_grade(state: AgentState) -> str:
    if state.get("relevant"):
        return "generate"
    return "rewrite_query" if state.get("attempts", 0) < MAX_REWRITES else "veil"


def route_after_rewrite(state: AgentState) -> str:
    return "veil" if state.get("off_topic") else "retrieve"


def build_graph(deps: Deps):
    g = StateGraph(AgentState)
    g.add_node("guard", nodes.make_guard())
    g.add_node("retrieve", nodes.make_retrieve(deps))
    g.add_node("grade", nodes.make_grade(deps))
    g.add_node("rewrite_query", nodes.make_rewrite(deps))
    g.add_node("generate", nodes.make_generate(deps))
    g.add_node("verdict", nodes.make_verdict(deps))
    g.add_node("refuse", nodes.refuse)
    g.add_node("veil", nodes.veil)

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", route_after_guard, {"refuse": "refuse", "retrieve": "retrieve"})
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges(
        "grade",
        route_after_grade,
        {"generate": "generate", "rewrite_query": "rewrite_query", "veil": "veil"},
    )
    g.add_conditional_edges(
        "rewrite_query", route_after_rewrite, {"veil": "veil", "retrieve": "retrieve"}
    )
    g.add_edge("generate", "verdict")
    for terminal in ("verdict", "refuse", "veil"):
        g.add_edge(terminal, END)
    return g.compile()
