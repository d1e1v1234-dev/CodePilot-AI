"""
review_code node: builds the review prompt (code + language + retrieved
context) and calls the existing GeminiService for a structured review.
"""

import logging
import time

from app.agents.state import ReviewState
from app.models.review import GeminiReviewOutput
from app.services.gemini import gemini_service, GeminiServiceError
from app.services.rag import RetrievedChunk

logger = logging.getLogger("codepilot.agents.review")

SYSTEM_INSTRUCTION = """\
You are a senior software engineer performing a strict code review.

Rules:
- Review ONLY the code provided by the user, in the programming
  language specified. Do not invent issues that are not actually
  present in the code.
- Apply the conventions, common pitfalls, and best practices specific
  to the stated language. Do not apply Python-specific rules to
  non-Python code.
- You may be given supporting reference material (best practices,
  common errors, security guidelines). Use it only as background
  knowledge to inform your judgment. Do NOT assume something is an
  issue just because it is mentioned in the reference material — the
  issue must actually be present in the submitted code. Do NOT copy
  the reference text verbatim into your review; explain issues in
  your own words, specific to this code.
- If the code has no real issues, return an empty "issues" list.
- Every issue must reference the actual line number in the submitted
  code where it occurs, when applicable.
- severity must be one of: critical, high, medium, low, info.
- category must be one of: bug, security, performance, quality, best_practice.
- EVERY issue MUST include ALL of these non-empty fields: "severity",
  "category", "title", "description", "recommendation". Never omit
  any field on any issue, even when returning many issues at once.
- overall_score is an integer from 0 to 100 reflecting overall code
  health (100 = excellent, 0 = severely broken/unsafe).
- "strengths" should list genuine positive aspects of the code, if any.
  It is fine to leave "strengths" empty if there truly are none.
- Be precise, technical, and concise. Do not pad the review with
  filler commentary.
- Respond ONLY with data matching the required schema. Do not include
  any text outside the structured response.
"""


def _build_prompt(code: str, language: str, chunks: list[RetrievedChunk]) -> str:
    prompt_parts = [
        f"Review the following {language} code as a senior code reviewer.\n",
        f"```{language}",
        code,
        "```",
    ]

    if chunks:
        prompt_parts.append(
            "\nSupporting reference material (background knowledge only, "
            "not a checklist to blindly apply):"
        )
        for chunk in chunks:
            prompt_parts.append(f"\n[Source: {chunk.source}]\n{chunk.text}")

    return "\n".join(prompt_parts)


def review_code(state: ReviewState) -> ReviewState:
    code = state.get("code", "")
    language = state.get("language", "python")
    chunks = state.get("retrieved_chunks", []) or []

    prompt = _build_prompt(code, language, chunks)

    start = time.perf_counter()
    try:
        gemini_output = gemini_service.generate_structured(
            prompt=prompt,
            response_model=GeminiReviewOutput,
            system_instruction=SYSTEM_INSTRUCTION,
        )
    except GeminiServiceError as exc:
        elapsed = time.perf_counter() - start
        logger.info("[PERF] Gemini review: %.2fs", elapsed)
        return {"gemini_output": None, "error": str(exc)}

    elapsed = time.perf_counter() - start
    logger.info("[PERF] Gemini review: %.2fs", elapsed)

    return {"gemini_output": gemini_output, "error": None}