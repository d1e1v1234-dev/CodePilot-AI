"""
ValidationService: SAFE static validation of generated Python code.

Design:
- Never executes user or LLM-generated code.
- Step 1: `ast.parse` to catch syntax errors cheaply and reliably.
- Step 2: Ruff static analysis (subprocess, code passed via stdin,
  nothing on disk is executed) for lint/style/correctness issues.
- If Ruff itself is unavailable or errors out, we degrade to
  "validation could not be fully performed" rather than falsely
  claiming success.
"""

import ast
import json
import subprocess

from app.models.review import ValidationResult


class ValidationService:
    def validate(self, code: str) -> ValidationResult:
        if not code or not code.strip():
            return ValidationResult(
                valid=False,
                tool="ast",
                messages=["No code provided to validate."],
            )

        syntax_result = self._check_syntax(code)
        if not syntax_result.valid:
            return syntax_result

        return self._run_ruff(code)

    def _check_syntax(self, code: str) -> ValidationResult:
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return ValidationResult(
                valid=False,
                tool="ast",
                messages=[f"SyntaxError: {exc.msg} (line {exc.lineno})"],
            )
        return ValidationResult(valid=True, tool="ast", messages=[])

    def _run_ruff(self, code: str) -> ValidationResult:
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format", "json", "-"],
                input=code,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            return ValidationResult(
                valid=False,
                tool="none",
                messages=[
                    "Static validator (ruff) is not available on the "
                    "server; validation could not be performed."
                ],
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                valid=False,
                tool="ruff",
                messages=["Validation timed out."],
            )
        except Exception as exc:  # noqa: BLE001
            return ValidationResult(
                valid=False,
                tool="ruff",
                messages=[f"Validation failed to run: {type(exc).__name__}"],
            )

        # Ruff returns exit code 0 (no findings) or 1 (findings present).
        # Anything else (e.g. 2) indicates ruff itself errored.
        if result.returncode not in (0, 1):
            return ValidationResult(
                valid=False,
                tool="ruff",
                messages=[
                    "Ruff encountered an internal error while validating "
                    "the code."
                ],
            )

        try:
            findings = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return ValidationResult(
                valid=False,
                tool="ruff",
                messages=["Could not parse validator output."],
            )

        if not findings:
            return ValidationResult(valid=True, tool="ruff", messages=[])

        messages = [
            f"{f.get('code', '?')}: {f.get('message', 'Unknown issue')} "
            f"(line {f.get('location', {}).get('row', '?')})"
            for f in findings
        ]
        return ValidationResult(valid=False, tool="ruff", messages=messages)


# Single shared instance used across the app.
validation_service = ValidationService()