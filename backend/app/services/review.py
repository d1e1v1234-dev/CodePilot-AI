"""
ReviewService: public entry point for code review + fix generation.
Invokes the compiled LangGraph workflow, passing along the selected
language so every node can adapt its behavior accordingly.

Language validation happens at the API boundary (main.py) — by the
time review_code() is called, `language` is guaranteed to already be
a member of SUPPORTED_LANGUAGES. This service does NOT silently
normalize an unsupported language to Python; "python" is only used
as a default when the caller passes an empty/None language.
"""

import logging
import time

from app.agents.graph import review_graph
from app.agents.state import ReviewState
from app.models.review import ReviewResponse

logger = logging.getLogger("codepilot.services.review")


class ReviewServiceError(Exception):
    """Raised when a code review cannot be produced."""


class ReviewService:
    def review_code(self, code: str, language: str | None = "python") -> ReviewResponse:
        if not code or not code.strip():
            raise ReviewServiceError("Code must not be empty.")

        # Default only applies when language is omitted/empty. Any
        # non-empty, unsupported language must be rejected upstream
        # (in the API route) before this method is ever called.
        resolved_language = (language or "python").strip().lower()

        initial_state: ReviewState = {
            "code": code,
            "language": resolved_language,
            "retry_count": 0,
        }

        start = time.perf_counter()
        try:
            final_state: ReviewState = review_graph.invoke(initial_state)
        except Exception as exc:  # noqa: BLE001 - never leak internals
            elapsed = time.perf_counter() - start
            logger.info("[PERF] Total review: %.2fs", elapsed)
            raise ReviewServiceError(
                "Failed to complete the code review workflow."
            ) from exc

        elapsed = time.perf_counter() - start
        logger.info("[PERF] Total review: %.2fs", elapsed)

        error = final_state.get("error")
        if error:
            raise ReviewServiceError(error)

        response = final_state.get("response")
        if response is None:
            raise ReviewServiceError("Code review did not produce a result.")

        response.language = resolved_language
        return response


# Single shared instance used across the app.
review_service = ReviewService()