"""
CodePilot AI Backend.

Exposes:
    GET  /api/health          - basic health check
    POST /api/test-gemini     - sanity-check the Gemini connection
    POST /api/review          - AI code review (RAG + LangGraph + fixes)
    POST /api/extract-code    - image -> code extraction
"""

import logging
import time

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.models.review import ReviewRequest, ReviewResponse, SUPPORTED_LANGUAGES
from app.models.extract import ExtractCodeResponse
from app.services.gemini import gemini_service, GeminiServiceError
from app.services.review import review_service, ReviewServiceError
from app.services.extract import extract_service, ExtractServiceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("codepilot")

ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB

app = FastAPI(title="CodePilot AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas (health / test-gemini) ----------

class HealthResponse(BaseModel):
    status: str
    service: str


class TestGeminiRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt to send to Gemini.")


class TestGeminiResponse(BaseModel):
    response: str


# ---------- Routes ----------

@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="CodePilot AI Backend")


@app.post("/api/test-gemini", response_model=TestGeminiResponse)
def test_gemini(payload: TestGeminiRequest) -> TestGeminiResponse:
    prompt = payload.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    try:
        result = gemini_service.generate_text(prompt)
    except GeminiServiceError as exc:
        logger.warning("Gemini request failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error while calling Gemini")
        raise HTTPException(
            status_code=500, detail="Internal server error."
        ) from exc

    return TestGeminiResponse(response=result)


@app.post("/api/review", response_model=ReviewResponse)
def review_code(payload: ReviewRequest) -> ReviewResponse:
    request_start = time.perf_counter()
    code = payload.code.strip()

    if not code:
        raise HTTPException(status_code=400, detail="Code must not be empty.")

    language = (payload.language or "python").strip().lower()

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported language '{payload.language}'. "
                f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}."
            ),
        )

    try:
        result = review_service.review_code(code, language)
    except ReviewServiceError as exc:
        logger.warning("Code review failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error during code review")
        raise HTTPException(
            status_code=500, detail="Internal server error."
        ) from exc
    else:
        elapsed = time.perf_counter() - request_start
        logger.info("[PERF] Total request (/api/review): %.2fs", elapsed)
        return result


@app.post("/api/extract-code", response_model=ExtractCodeResponse)
async def extract_code(file: UploadFile = File(...)) -> ExtractCodeResponse:
    request_start = time.perf_counter()

    if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Allowed types: "
                "PNG, JPG/JPEG, WEBP."
            ),
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image is too large. Maximum allowed size is 8 MB.",
        )

    try:
        gemini_start = time.perf_counter()
        result = extract_service.extract_code(image_bytes, file.content_type)
        gemini_elapsed = time.perf_counter() - gemini_start
        logger.info("[PERF] Gemini extraction: %.2fs", gemini_elapsed)
    except ExtractServiceError as exc:
        logger.warning("Code extraction failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - final safety net
        logger.exception("Unexpected error during code extraction")
        raise HTTPException(
            status_code=500, detail="Internal server error."
        ) from exc
    else:
        elapsed = time.perf_counter() - request_start
        logger.info("[PERF] Total request (/api/extract-code): %.2fs", elapsed)
        return result
    finally:
        await file.close()