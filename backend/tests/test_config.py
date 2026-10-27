import pytest
from pydantic import ValidationError

from tests.conftest import make_settings


def test_blank_api_key_counts_as_not_configured() -> None:
    assert make_settings(gemini_api_key="   ").llm_configured is False


def test_api_key_is_masked_in_repr() -> None:
    settings = make_settings(gemini_api_key="super-secret-value")

    assert settings.llm_configured is True
    assert "super-secret-value" not in repr(settings)


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = make_settings(cors_origins=" http://a.test , ,http://b.test ")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize("value", [0, 51])
def test_upload_limit_is_bounded(value: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(max_upload_mb=value)
