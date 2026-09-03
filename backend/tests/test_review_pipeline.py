"""
Tests for the fix-generation + validation + retry pipeline. Gemini
calls are mocked so tests run without network access or a real API
key.
"""

from unittest.mock import patch

from app.models.review import (
    Category,
    FixOutput,
    GeminiReviewOutput,
    ReviewIssue,
    Severity,
    ValidationResult,
)
from app.services.review import review_service


def _fake_review_output():
    return GeminiReviewOutput(
        summary="Test summary",
        overall_score=60,
        issues=[
            ReviewIssue(
                severity=Severity.MEDIUM,
                category=Category.BUG,
                title="Missing zero check",
                line=1,
                description="No check for zero divisor.",
                recommendation="Add a check.",
            )
        ],
        strengths=["Simple function"],
    )


def _fake_fix_output(changed=True, code="def divide(a, b):\n    if b == 0:\n        raise ValueError('b must not be 0')\n    return a / b\n"):
    return FixOutput(
        fixed_code=code,
        explanation="Added a zero-division guard.",
        changed=changed,
    )


@patch("app.agents.nodes.generate_fix.gemini_service")
@patch("app.agents.nodes.review.gemini_service")
@patch("app.agents.nodes.retrieve.rag_service")
def test_fix_generation_and_validation_success(mock_rag, mock_review_gemini, mock_fix_gemini):
    mock_rag.retrieve.return_value = []
    mock_review_gemini.generate_structured.return_value = _fake_review_output()
    mock_fix_gemini.generate_structured.return_value = _fake_fix_output()

    result = review_service.review_code("def divide(a, b): return a / b")

    assert result.fixed_code is not None
    assert result.fix_explanation == "Added a zero-division guard."
    assert result.validation is not None
    assert result.validation.tool in ("ast", "ruff")


@patch("app.agents.nodes.generate_fix.gemini_service")
@patch("app.agents.nodes.review.gemini_service")
@patch("app.agents.nodes.retrieve.rag_service")
def test_no_issues_skips_fix_generation(mock_rag, mock_review_gemini, mock_fix_gemini):
    mock_rag.retrieve.return_value = []
    mock_review_gemini.generate_structured.return_value = GeminiReviewOutput(
        summary="Clean code",
        overall_score=95,
        issues=[],
        strengths=["Well written"],
    )

    result = review_service.review_code("def add(a: int, b: int) -> int:\n    return a + b\n")

    assert result.validation.tool == "none"
    mock_fix_gemini.generate_structured.assert_not_called()


@patch("app.agents.nodes.generate_fix.gemini_service")
@patch("app.agents.nodes.review.gemini_service")
@patch("app.agents.nodes.retrieve.rag_service")
def test_retry_limit_is_respected(mock_rag, mock_review_gemini, mock_fix_gemini):
    mock_rag.retrieve.return_value = []
    mock_review_gemini.generate_structured.return_value = _fake_review_output()

    # Always return code that fails validation (syntax error) so the
    # graph is forced to retry until it hits the max retry limit.
    mock_fix_gemini.generate_structured.return_value = _fake_fix_output(
        changed=True, code="def broken(:\n    pass\n"
    )

    result = review_service.review_code("def divide(a, b): return a / b")

    assert result.retry_count == 2  # MAX_RETRIES
    assert result.validation.valid is False
    assert mock_fix_gemini.generate_structured.call_count == 3  # initial + 2 retries


def test_review_endpoint_still_works_end_to_end_shape():
    """
    Confirms review_code always returns a ReviewResponse with the
    original Step 1-4 fields present, regardless of fix/validation
    outcome (structural backward-compatibility check).
    """
    with patch("app.agents.nodes.retrieve.rag_service") as mock_rag, \
         patch("app.agents.nodes.review.gemini_service") as mock_review_gemini, \
         patch("app.agents.nodes.generate_fix.gemini_service") as mock_fix_gemini:
        mock_rag.retrieve.return_value = []
        mock_review_gemini.generate_structured.return_value = GeminiReviewOutput(
            summary="ok", overall_score=80, issues=[], strengths=[]
        )

        result = review_service.review_code("x = 1\n")

        assert hasattr(result, "summary")
        assert hasattr(result, "overall_score")
        assert hasattr(result, "issues")
        assert hasattr(result, "strengths")
        assert hasattr(result, "sources")
        mock_fix_gemini.generate_structured.assert_not_called()