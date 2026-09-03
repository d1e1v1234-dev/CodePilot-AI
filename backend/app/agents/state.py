"""
Typed state shared across all LangGraph nodes for the code review +
fix-generation workflow.
"""

from typing import TypedDict

from app.models.review import FixOutput, GeminiReviewOutput, ReviewResponse, ValidationResult
from app.services.rag import RetrievedChunk


class ReviewState(TypedDict, total=False):
    # Input
    code: str  # original, unmodified user code
    language: str  # e.g. "python", "javascript", "sql"

    # Populated by retrieve_context node
    retrieved_chunks: list[RetrievedChunk]

    # Populated by review_code node
    gemini_output: GeminiReviewOutput | None
    error: str | None

    # Populated by generate_fix node
    fixed_code: str | None
    fix_explanation: str | None
    fix_changed: bool

    # Populated by validate_fix node
    validation: ValidationResult | None
    retry_count: int

    # Populated by decision/finalize node
    response: ReviewResponse | None