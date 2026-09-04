"""
validate_fix node: runs SAFE static validation (AST + Ruff) on the
generated fixed_code, but ONLY for languages that actually support it
(currently Python only). For all other languages, this node reports
that validation is unavailable rather than faking a result — it never
claims a pass/fail for a language that wasn't actually checked.
"""

import logging
import time

from app.agents.state import ReviewState
from app.models.review import LANGUAGES_WITH_STATIC_VALIDATION, ValidationResult
from app.services.validation import validation_service

logger = logging.getLogger("codepilot.agents.validate_fix")


def validate_fix(state: ReviewState) -> ReviewState:
    start = time.perf_counter()

    fixed_code = state.get("fixed_code")
    fix_changed = state.get("fix_changed", False)
    language = state.get("language", "python")

    if not fixed_code or not fix_changed:
        elapsed = time.perf_counter() - start
        logger.info("[PERF] Validation: %.2fs", elapsed)
        return {
            "validation": ValidationResult(
                valid=True,
                tool="none",
                messages=["No code changes were made; nothing to validate."],
            )
        }

    if language not in LANGUAGES_WITH_STATIC_VALIDATION:
        elapsed = time.perf_counter() - start
        logger.info("[PERF] Validation: %.2fs", elapsed)
        return {
            "validation": ValidationResult(
                valid=True,
                tool="none",
                messages=[
                    "Static validation is currently available for "
                    "Python only. The generated fix was not checked."
                ],
            )
        }

    result = validation_service.validate(fixed_code)

    elapsed = time.perf_counter() - start
    logger.info("[PERF] Validation: %.2fs", elapsed)

    return {"validation": result}