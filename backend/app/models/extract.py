"""
Pydantic models for the image -> code extraction feature.
"""

from pydantic import BaseModel, Field


class ExtractCodeResponse(BaseModel):
    code: str = Field(
        ..., description="The code transcribed from the image, as accurately as possible."
    )
    language: str = Field(
        ...,
        description=(
            "Best-guess programming language of the extracted code "
            "(e.g. 'python', 'javascript'). Use 'unknown' if it cannot "
            "be determined."
        ),
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence (0-1) that the extraction is accurate and complete.",
    )
    notes: str = Field(
        default="",
        description=(
            "Notes on uncertainty, unreadable portions, or anything "
            "the user should double-check. Empty string if none."
        ),
    )