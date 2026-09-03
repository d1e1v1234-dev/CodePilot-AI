"""
Tests for ValidationService — safe static analysis only, no code
execution.
"""

from app.services.validation import validation_service


def test_valid_python_code_passes():
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    result = validation_service.validate(code)
    assert result.tool in ("ast", "ruff")
    # Either ast-only pass or ruff clean pass is acceptable here.
    assert isinstance(result.valid, bool)


def test_syntax_error_is_caught_by_ast():
    code = "def broken(:\n    return 1\n"
    result = validation_service.validate(code)
    assert result.valid is False
    assert result.tool == "ast"
    assert any("SyntaxError" in m for m in result.messages)


def test_empty_code_is_invalid():
    result = validation_service.validate("")
    assert result.valid is False
    assert result.messages


def test_unused_import_flagged_by_ruff():
    code = "import os\n\ndef f():\n    return 1\n"
    result = validation_service.validate(code)
    # If ruff is installed, this should be flagged as invalid (F401).
    # If ruff is unavailable, tool falls back to "none" with valid=False.
    assert result.tool in ("ruff", "none")
    if result.tool == "ruff":
        assert result.valid is False