"""
generate_fix node: if the review found issues, asks Gemini to produce
corrected code + an explanation, structured via FixOutput.

Note: this node is only reached by the graph when review_code found
actual issues in the issues list (see agents/nodes/decision.py's
route_after_review and agents/graph.py) — so the "no issues" guard
below is now mostly a defensive fallback rather than the primary
mechanism for skipping the Gemini call.
"""

import logging
import time

from app.agents.state import ReviewState
from app.models.review import FixOutput
from app.services.gemini import gemini_service, GeminiServiceError

logger = logging.getLogger("codepilot.agents.generate_fix")

SYSTEM_INSTRUCTION = """\
You are a senior software engineer fixing bugs found in a code review.

Rules:
- Only change what is necessary to resolve the reported issues. Do
  not rewrite unrelated parts of the code or change its behavior
  beyond what is required.
- Return the FULL corrected file in "fixed_code", not a diff/patch,
  in the same programming language as the original.
- If none of the reported issues are actually fixable in code (e.g.
  they are purely informational), set "changed" to false and return
  the original code unchanged in "fixed_code".
- "explanation" must clearly and concisely describe what was changed
  and why, in plain language.
- The output code must be syntactically valid in the stated language.
- Do not invent new issues to fix beyond what was reported.
- Respond ONLY with data matching the required schema.
"""


def generate_fix(state: ReviewState) -> ReviewState:
    gemini_output = state.get("gemini_output")
    original_code = state.get("code", "")
    language = state.get("language", "python")
    retry_count = state.get("retry_count", 0)

    if gemini_output is None:
        return {
            "fixed_code": None,
            "fix_explanation": None,
            "fix_changed": False,
        }

    if not gemini_output.issues:
        return {
            "fixed_code": original_code,
            "fix_explanation": "No fixable issues were found.",
            "fix_changed": False,
        }

    issues_text = "\n".join(
        f"- [{issue.severity.value}/{issue.category.value}] {issue.title} "
        f"(line {issue.line}): {issue.description} "
        f"Suggested fix: {issue.recommendation}"
        for issue in gemini_output.issues
    )

    prompt_parts = [
        f"Fix the following {language} code based on the issues found "
        "in a code review.\n",
        f"```{language}",
        original_code,
        "```",
        "\nIssues to fix:",
        issues_text,
    ]

    validation = state.get("validation")
    if retry_count > 0 and validation is not None and not validation.valid:
        prompt_parts.append(
            "\nYour previous fix attempt failed validation "
            f"(tool: {validation.tool}) with these problems:\n"
            + "\n".join(f"- {m}" for m in validation.messages)
            + "\nPlease produce a corrected version that resolves these "
            "validation problems as well."
        )

    prompt = "\n".join(prompt_parts)

    start = time.perf_counter()
    try:
        fix_output: FixOutput = gemini_service.generate_structured(
            prompt=prompt,
            response_model=FixOutput,
            system_instruction=SYSTEM_INSTRUCTION,
        )
    except GeminiServiceError as exc:
        elapsed = time.perf_counter() - start
        logger.info("[PERF] Gemini fix: %.2fs", elapsed)
        return {
            "error": f"Fix generation failed: {exc}",
            "fixed_code": None,
            "fix_explanation": None,
            "fix_changed": False,
        }

    elapsed = time.perf_counter() - start
    logger.info("[PERF] Gemini fix: %.2fs", elapsed)

    return {
        "fixed_code": fix_output.fixed_code,
        "fix_explanation": fix_output.explanation,
        "fix_changed": fix_output.changed,
        "error": None,
    }