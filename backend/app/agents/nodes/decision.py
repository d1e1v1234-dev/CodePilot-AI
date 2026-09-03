"""
decision node: finalizes the workflow output once validation has
either passed or the retry budget is exhausted. Also exposes a router
function used by the graph's conditional edges to decide whether to
retry generate_fix, or stop.
"""

from app.agents.state import ReviewState
from app.models.review import ReviewResponse, SourceReference

MAX_RETRIES = 2


def finalize(state: ReviewState) -> ReviewState:
    if state.get("error"):
        return {"response": None}

    gemini_output = state.get("gemini_output")
    if gemini_output is None:
        return {
            "error": "Gemini returned no review output.",
            "response": None,
        }

    chunks = state.get("retrieved_chunks", []) or []
    sources = [
        SourceReference(name=chunk.source, relevance=chunk.relevance)
        for chunk in chunks
    ]

    validation = state.get("validation")

    response = ReviewResponse(
        summary=gemini_output.summary,
        overall_score=gemini_output.overall_score,
        issues=gemini_output.issues,
        strengths=gemini_output.strengths,
        sources=sources,
        fixed_code=state.get("fixed_code"),
        fix_explanation=state.get("fix_explanation"),
        validation=validation,
        retry_count=state.get("retry_count", 0),
    )

    return {"response": response}


def route_after_decision(state: ReviewState) -> str:
    """
    Conditional edge router, called after the `decision` node runs.
    Returns the name of the next node ("generate_fix") or "END".
    """
    if state.get("error"):
        return "END"

    validation = state.get("validation")
    if validation is None or validation.valid:
        return "END"

    fix_changed = state.get("fix_changed", False)
    if not fix_changed:
        # Nothing was actually changed, so retrying won't help.
        return "END"

    retry_count = state.get("retry_count", 0)
    if retry_count >= MAX_RETRIES:
        return "END"

    return "generate_fix"


def increment_retry(state: ReviewState) -> ReviewState:
    """Small helper node to bump retry_count before looping back."""
    return {"retry_count": state.get("retry_count", 0) + 1}