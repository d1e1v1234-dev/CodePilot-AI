"""
ExtractService: builds the image-to-code extraction prompt and calls
GeminiService's multimodal method to get structured, validated
ExtractCodeResponse output.
"""

from app.models.extract import ExtractCodeResponse
from app.services.gemini import gemini_service, GeminiServiceError

SYSTEM_INSTRUCTION = """\
You are transcribing source code from an image with extreme accuracy.

Rules:
- Transcribe the code EXACTLY as shown: preserve indentation, spacing,
  line breaks, punctuation, and casing.
- Do NOT add explanations, comments, or markdown formatting inside the
  "code" field. Return only the raw source code.
- Do NOT invent, guess, or complete any code that is not clearly
  visible in the image. If part of the code is cut off, blurry, or
  ambiguous, leave that portion out or mark it clearly with a comment
  like "# unreadable" at that location, and describe the issue in
  "notes".
- Identify the programming language as accurately as possible. Use
  "unknown" if it truly cannot be determined.
- "confidence" must reflect your actual certainty in the accuracy and
  completeness of the transcription (1.0 = fully confident and
  complete, lower values for partial/uncertain reads).
- "notes" must mention any uncertainty, unreadable regions, cropped
  content, or reasons for a lower confidence score. Leave it as an
  empty string only if you are fully confident and nothing is unclear.
- If the image does not contain any visible source code at all, set
  "code" to an empty string, "language" to "unknown", "confidence" to
  0.0, and explain this in "notes".
- Respond ONLY with data matching the required schema.
"""

EXTRACTION_PROMPT = (
    "Transcribe all source code visible in this image, following your "
    "instructions exactly."
)


class ExtractServiceError(Exception):
    """Raised when code extraction from an image cannot be produced."""


class ExtractService:
    def extract_code(self, image_bytes: bytes, mime_type: str) -> ExtractCodeResponse:
        if not image_bytes:
            raise ExtractServiceError("Image data must not be empty.")

        try:
            return gemini_service.generate_structured_from_image(
                image_bytes=image_bytes,
                mime_type=mime_type,
                prompt=EXTRACTION_PROMPT,
                response_model=ExtractCodeResponse,
                system_instruction=SYSTEM_INSTRUCTION,
            )
        except GeminiServiceError as exc:
            raise ExtractServiceError(str(exc)) from exc


# Single shared instance used across the app.
extract_service = ExtractService()