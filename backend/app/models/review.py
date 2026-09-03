"""
Pydantic models for the code review + fix-generation feature.
"""

from enum import Enum

from pydantic import BaseModel, Field

SUPPORTED_LANGUAGES = [
    "python",
    "cpp",
    "java",
    "javascript",
    "typescript",
    "html",
    "css",
    "sql",
]

# Only Python has real static validation (AST + Ruff) implemented.
LANGUAGES_WITH_STATIC_VALIDATION = {"python"}


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Category(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    BEST_PRACTICE = "best_practice"


class ReviewRequest(BaseModel):
    code: str = Field(..., description="Source code to review.")
    language: str = Field(
        default="python",
        description=(
            "Programming language of the submitted code. Defaults to "
            "'python' for backward compatibility with clients that "
            "only send {'code': ...}."
        ),
    )


class ReviewIssue(BaseModel):
    severity: Severity = Field(..., description="How serious this issue is.")
    category: Category = Field(..., description="The type of issue.")
    title: str = Field(..., 
                       description="Required, non-empty. A short title (a few words) "
                                    "summarizing the issue. This field must always be "
                                    "included for every issue — never omit it.")
    line: int | None = Field(
        default=None, description="1-based line number, if applicable."
    )
    description: str = Field(
        ...,
        description=(
            "Required. A clear, specific explanation of what the "
            "issue is and why it matters. Must never be empty."
        ),
    )
    recommendation: str = Field(
        ...,
        description=(
            "Required. A concrete, actionable fix for this issue. "
            "Must never be empty."
        ),
    )


class SourceReference(BaseModel):
    name: str
    relevance: float = Field(..., ge=0.0, le=1.0)


class GeminiReviewOutput(BaseModel):
    """Schema Gemini is constrained to produce for the review step."""

    summary: str
    overall_score: int = Field(..., ge=0, le=100)
    issues: list[ReviewIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)


class FixOutput(BaseModel):
    fixed_code: str = Field(
        ..., description="The full corrected source code."
    )
    explanation: str = Field(
        ...,
        description="A concise explanation of what was changed and why.",
    )
    changed: bool = Field(
        ...,
        description=(
            "True if the code was actually modified. False if no "
            "fixable issues were found and the code was left as-is."
        ),
    )


class ValidationResult(BaseModel):
    """
    Result of static validation performed on generated fixed code.
    `valid` must only ever be True when actual static analysis
    passed, or when validation is not applicable for the given
    language (in which case `tool` is "none" and `messages" explains
    why).
    """

    valid: bool
    tool: str = Field(..., description="Which validator produced this result.")
    messages: list[str] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    summary: str = Field(..., description="A short overall summary of the review.")
    overall_score: int = Field(..., ge=0, le=100)
    issues: list[ReviewIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)

    fixed_code: str | None = None
    fix_explanation: str | None = None
    validation: ValidationResult | None = None
    retry_count: int = 0
    language: str = "python"