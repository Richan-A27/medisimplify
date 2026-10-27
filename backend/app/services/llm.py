"""LLM access behind a small protocol so tests and evaluation can swap the backend.

Every failure is mapped to an `LLMError` with a user-safe message. Prompts and responses are never logged.
"""

import time
from dataclasses import dataclass
from typing import Protocol

from app.prompts.builder import PromptBundle
from app.schemas.summary import TokenUsage


class LLMError(Exception):
    code = "llm_error"
    status_code = 502
    message = "The language model request failed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class LLMNotConfiguredError(LLMError):
    code = "llm_not_configured"
    status_code = 503
    message = "No Gemini API key is configured. Add GEMINI_API_KEY to .env and restart the backend."


class LLMQuotaError(LLMError):
    code = "llm_quota_exceeded"
    status_code = 429
    message = "The Gemini API quota or rate limit was reached. Wait a minute and try again."


class LLMAuthError(LLMError):
    code = "llm_auth_failed"
    message = "The Gemini API rejected the API key. Check GEMINI_API_KEY."


class LLMTimeoutError(LLMError):
    code = "llm_timeout"
    status_code = 504
    message = "The language model did not respond in time. Please try again."


class LLMUnavailableError(LLMError):
    code = "llm_unavailable"
    status_code = 503
    message = "The language model service is temporarily unavailable. Please try again later."


class LLMBadRequestError(LLMError):
    code = "llm_bad_request"
    message = "The language model rejected the request (check GEMINI_MODEL)."


class LLMEmptyResponseError(LLMError):
    code = "llm_no_output"
    message = "The language model returned no usable output (it may have been blocked by safety filters)."


class LLMInvalidOutputError(LLMError):
    code = "llm_invalid_output"
    message = "The language model returned output that does not match the required format."


@dataclass(frozen=True)
class GenerationSettings:
    temperature: float
    seed: int
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    usage: TokenUsage
    latency_ms: int


class LLMClient(Protocol):
    model: str

    def generate(self, prompt: PromptBundle) -> LLMResult: ...


class GeminiClient:
    def __init__(self, api_key: str, model: str, settings: GenerationSettings) -> None:
        from google import genai  # deferred: only needed when summaries are requested
        from google.genai import types

        self.model = model
        self.settings = settings
        self._types = types
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(settings.timeout_seconds * 1000)),
        )

    def generate(self, prompt: PromptBundle) -> LLMResult:
        from google.genai import errors

        types = self._types
        config = types.GenerateContentConfig(
            system_instruction=prompt.system_instruction,
            temperature=self.settings.temperature,
            seed=self.settings.seed,
            max_output_tokens=self.settings.max_output_tokens,
            response_mime_type="application/json",
            response_json_schema=prompt.response_schema,
        )
        contents = [
            types.Content(role=message.role, parts=[types.Part(text=message.text)]) for message in prompt.messages
        ]
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(model=self.model, contents=contents, config=config)
        except errors.APIError as exc:
            raise _map_api_error(exc) from exc
        except Exception as exc:
            if _is_timeout(exc):
                raise LLMTimeoutError() from exc
            raise LLMUnavailableError() from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = response.text if response.candidates else None
        if not text:
            raise LLMEmptyResponseError()
        meta = response.usage_metadata
        usage = TokenUsage(
            prompt_tokens=getattr(meta, "prompt_token_count", None),
            output_tokens=getattr(meta, "candidates_token_count", None),
            total_tokens=getattr(meta, "total_token_count", None),
        )
        return LLMResult(text=text, model=self.model, usage=usage, latency_ms=latency_ms)


def _map_api_error(exc: Exception) -> LLMError:
    code = getattr(exc, "code", None)
    if code == 429:
        return LLMQuotaError()
    if code in (401, 403):
        return LLMAuthError()
    if code == 400 and "API key" in str(exc):
        return LLMAuthError()
    if code in (400, 404):
        return LLMBadRequestError()
    if code in (408, 504):
        return LLMTimeoutError()
    return LLMUnavailableError()


def _is_timeout(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, TimeoutError) or "Timeout" in type(current).__name__:
            return True
        current = current.__cause__ or current.__context__
    return False
