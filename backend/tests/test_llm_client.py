from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors

from app.prompts.builder import build_prompt
from app.services.llm import (
    GeminiClient,
    GenerationSettings,
    LLMAuthError,
    LLMBadRequestError,
    LLMEmptyResponseError,
    LLMQuotaError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.pdf_extraction import PageText
from app.services.report_parser import parse_measurements
from scripts.synthetic_reports import REPORTS

SETTINGS = GenerationSettings(temperature=0.2, seed=42, max_output_tokens=1024, timeout_seconds=30)
PROMPT = build_prompt("few_shot", parse_measurements([PageText(1, "\n".join(REPORTS["cbc_normal"]))]), [])


class FakeModels:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def client_returning(result: Any) -> tuple[GeminiClient, FakeModels]:
    client = GeminiClient(api_key="test-key", model="gemini-test", settings=SETTINGS)
    models = FakeModels(result)
    client._client = SimpleNamespace(models=models)  # type: ignore[assignment]
    return client, models


def api_error(code: int, status: str, message: str = "error") -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "status": status, "message": message}})


def test_sends_fixed_settings_schema_and_roles() -> None:
    response = SimpleNamespace(
        text='{"summary": "x"}',
        candidates=[object()],
        usage_metadata=SimpleNamespace(prompt_token_count=120, candidates_token_count=80, total_token_count=200),
    )
    client, models = client_returning(response)

    result = client.generate(PROMPT)

    call = models.calls[0]
    config = call["config"]
    assert call["model"] == "gemini-test"
    assert (config.temperature, config.seed, config.max_output_tokens) == (0.2, 42, 1024)
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == PROMPT.response_schema
    assert config.system_instruction == PROMPT.system_instruction
    assert [c.role for c in call["contents"]] == ["user", "model", "user", "model", "user"]
    assert result.text == '{"summary": "x"}'
    assert (result.usage.prompt_tokens, result.usage.output_tokens, result.usage.total_tokens) == (120, 80, 200)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api_error(429, "RESOURCE_EXHAUSTED", "Quota exceeded"), LLMQuotaError),
        (api_error(403, "PERMISSION_DENIED"), LLMAuthError),
        (api_error(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key."), LLMAuthError),
        (api_error(404, "NOT_FOUND", "models/gemini-x is not found"), LLMBadRequestError),
        (api_error(503, "UNAVAILABLE"), LLMUnavailableError),
        (api_error(504, "DEADLINE_EXCEEDED"), LLMTimeoutError),
        (httpx.ReadTimeout("timed out"), LLMTimeoutError),
        (ConnectionError("network down"), LLMUnavailableError),
    ],
)
def test_errors_are_mapped(error: BaseException, expected: type) -> None:
    client, _ = client_returning(error)

    with pytest.raises(expected):
        client.generate(PROMPT)


def test_quota_error_status_and_message() -> None:
    client, _ = client_returning(api_error(429, "RESOURCE_EXHAUSTED"))

    with pytest.raises(LLMQuotaError) as info:
        client.generate(PROMPT)
    assert info.value.status_code == 429
    assert "quota" in info.value.message.lower()


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(text=None, candidates=[], usage_metadata=None),
        SimpleNamespace(text="", candidates=[object()], usage_metadata=None),
    ],
)
def test_empty_or_blocked_response(response: Any) -> None:
    client, _ = client_returning(response)

    with pytest.raises(LLMEmptyResponseError):
        client.generate(PROMPT)
