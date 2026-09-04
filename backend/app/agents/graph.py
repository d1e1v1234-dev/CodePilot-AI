"""
Compiles the code review + fix-generation LangGraph workflow:

    START -> retrieve_context -> review_code
          -> (conditional) -> generate_fix -> validate_fix -> decision   [issues found]
          -> (conditional) -> decision                                  [no issues / error]
          -> (conditional) -> increment_retry -> generate_fix  [retry, at most once]
          -> (conditional) -> END                              [done]

Each node reuses the existing RAGService/GeminiService/
ValidationService — no business logic is duplicated here, this file
only wires the steps together.
"""

from langgraph.graph import StateGraph, START, END

from app.agents.state import ReviewState
from app.agents.nodes.retrieve import retrieve_context
from app.agents.nodes.review import review_code
from app.agents.nodes.generate_fix import generate_fix
from app.agents.nodes.validate_fix import validate_fix
from app.agents.nodes.decision import (
    finalize,
    route_after_decision,
    route_after_review,
    increment_retry,
)


def build_review_graph():
    builder = StateGraph(ReviewState)

    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("review_code", review_code)
    builder.add_node("generate_fix", generate_fix)
    builder.add_node("validate_fix", validate_fix)
    builder.add_node("decision", finalize)
    builder.add_node("increment_retry", increment_retry)

    builder.add_edge(START, "retrieve_context")
    builder.add_edge("retrieve_context", "review_code")

    # If review found no meaningful issues (or review itself failed),
    # skip generate_fix and validate_fix entirely and go straight to
    # decision — this is what actually avoids the unnecessary Gemini
    # fix call and the validation pass, not just short-circuiting
    # inside those nodes.
    builder.add_conditional_edges(
        "review_code",
        route_after_review,
        {
            "generate_fix": "generate_fix",
            "decision": "decision",
        },
    )

    builder.add_edge("generate_fix", "validate_fix")
    builder.add_edge("validate_fix", "decision")

    builder.add_conditional_edges(
        "decision",
        route_after_decision,
        {
            "generate_fix": "increment_retry",
            "END": END,
        },
    )
    builder.add_edge("increment_retry", "generate_fix")

    return builder.compile()


# Compiled once at import time; reused across requests.
review_graph = build_review_graph()