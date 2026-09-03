"""
Tests for POST /api/extract-code. Gemini calls are mocked so tests
run without network access or a real API key.
"""

import io

from fastapi.testclient import TestClient

from app.main import app
from app.models.extract import ExtractCodeResponse

client = TestClient(app)

# 1x1 transparent PNG, valid minimal image bytes.
TINY_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415478da6360000002000155aa2b640000000049454e44ae42"
    "6082"
)


def test_unsupported_file_type_is_rejected():
    response = client.post(
        "/api/extract-code",
        files={"file": ("code.txt", b"print('hi')", "text/plain")},
    )
    assert response.status_code == 415


def test_oversized_file_is_rejected():
    oversized = b"0" * (9 * 1024 * 1024)  # 9 MB > 8 MB limit
    response = client.post(
        "/api/extract-code",
        files={"file": ("screenshot.png", oversized, "image/png")},
    )
    assert response.status_code == 413


def test_successful_extraction_with_mocked_gemini():
    fake_result = ExtractCodeResponse(
        code="def add(a, b):\n    return a + b\n",
        language="python",
        confidence=0.95,
        notes="",
    )

    from unittest.mock import patch

    with patch("app.services.extract.gemini_service") as mock_gemini:
        mock_gemini.generate_structured_from_image.return_value = fake_result

        response = client.post(
            "/api/extract-code",
            files={"file": ("screenshot.png", TINY_PNG_BYTES, "image/png")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "python"
    assert body["confidence"] == 0.95
    assert "def add" in body["code"]


def test_malformed_gemini_response_returns_502():
    from unittest.mock import patch

    from app.services.gemini import GeminiServiceError

    with patch("app.services.extract.gemini_service") as mock_gemini:
        mock_gemini.generate_structured_from_image.side_effect = GeminiServiceError(
            "Gemini returned a response that did not match the expected format."
        )

        response = client.post(
            "/api/extract-code",
            files={"file": ("screenshot.png", TINY_PNG_BYTES, "image/png")},
        )

    assert response.status_code == 502
    assert "api" not in response.json()["detail"].lower() or "key" not in response.json()["detail"].lower()


def test_empty_file_is_rejected():
    response = client.post(
        "/api/extract-code",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400