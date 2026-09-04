"""
GeminiService: a small, reusable wrapper around
langchain-google-genai's ChatGoogleGenerativeAI.

Keeping all Gemini-specific code in one place means routes (and other
services) never talk to LangChain/Gemini directly.
"""

from typing import TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ValidationError

from app.config import settings
import base64

from langchain_core.messages import HumanMessage

T = TypeVar("T", bound=BaseModel)


class GeminiServiceError(Exception):
    """Raised for any Gemini-related failure (config or API)."""


class GeminiService:
    def __init__(self) -> None:
        self._llm: ChatGoogleGenerativeAI | None = None

    def _get_llm(self) -> ChatGoogleGenerativeAI:
        """
        Lazily create the chat model on first use.
        """
        if self._llm is None:
            if not settings.GEMINI_API_KEY:
                raise GeminiServiceError(
                    "GEMINI_API_KEY is not configured on the server."
                )
            self._llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
            )
        return self._llm

    def generate_text(self, prompt: str) -> str:
        """
        Send a text prompt to Gemini and return the generated text.
        """
        if not prompt or not prompt.strip():
            raise GeminiServiceError("Prompt must not be empty.")

        llm = self._get_llm()

        try:
            result = llm.invoke(prompt)
        except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
            raise GeminiServiceError(
                "Failed to get a response from Gemini."
            ) from exc

        text = getattr(result, "content", None)
        if not text:
            raise GeminiServiceError("Gemini returned an empty response.")

        return text

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        max_attempts: int = 1,
    ) -> T:
        """
        Send a prompt to Gemini and force the output to match
        `response_model`'s schema using LangChain's structured output.
        Returns a validated instance of `response_model`.

        MVP default is a single attempt (max_attempts=1): no
        self-correction retry round-trip. If the response fails
        schema validation, this raises a clean GeminiServiceError
        immediately instead of re-prompting Gemini. Callers that
        genuinely need the self-correction retry can still pass a
        higher `max_attempts` explicitly.

        Raises:
            GeminiServiceError: on missing key, empty prompt, API
            failure, or a response that still fails validation after
            all attempts.
        """
        if not prompt or not prompt.strip():
            raise GeminiServiceError("Prompt must not be empty.")

        llm = self._get_llm()
        structured_llm = llm.with_structured_output(response_model)

        last_error: Exception | None = None
        current_prompt = prompt

        for attempt in range(1, max_attempts + 1):
            messages = []
            if system_instruction:
                messages.append(("system", system_instruction))
            messages.append(("human", current_prompt))

            try:
                result = structured_llm.invoke(messages)
            except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
                raise GeminiServiceError(
                    "Failed to get a response from Gemini."
                ) from exc

            if isinstance(result, response_model):
                return result

            try:
                return response_model.model_validate(result)
            except ValidationError as exc:
                last_error = exc
                if attempt < max_attempts:
                    current_prompt = (
                        f"{prompt}\n\n"
                        "Your previous response was missing required fields "
                        f"and failed validation with this error:\n{exc}\n\n"
                        "Please respond again, making sure every required "
                        "field is present and non-empty for every item."
                    )
                    continue

        raise GeminiServiceError(
            "Gemini returned a response that did not match the "
            "expected format."
        ) from last_error

    def generate_structured_from_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """
        Send an image + text prompt to Gemini and force the output to
        match `response_model`'s schema. Used for multimodal tasks
        like image-to-code extraction.

        Raises:
            GeminiServiceError: on missing key, API failure, or a
            response that fails schema validation.
        """
        if not image_bytes:
            raise GeminiServiceError("Image data must not be empty.")

        llm = self._get_llm()
        structured_llm = llm.with_structured_output(response_model)

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        image_data_url = f"data:{mime_type};base64,{encoded_image}"

        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": image_data_url},
        ]

        messages = []
        if system_instruction:
            messages.append(("system", system_instruction))
        messages.append(HumanMessage(content=content))

        try:
            result = structured_llm.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - normalize all SDK errors
            raise GeminiServiceError(
                "Failed to get a response from Gemini."
            ) from exc

        if isinstance(result, response_model):
            return result

        try:
            return response_model.model_validate(result)
        except ValidationError as exc:
            raise GeminiServiceError(
                "Gemini returned a response that did not match the "
                "expected format."
            ) from exc


# Single shared instance used across the app.
gemini_service = GeminiService()