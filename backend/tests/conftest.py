import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(**overrides: object) -> Settings:
    """Settings isolated from the developer's real `.env` and environment."""
    base: dict[str, object] = {
        "app_env": "test",
        "gemini_api_key": None,
        # Never touch the real index from unit tests.
        "knowledge_base_dir": Path("/nonexistent") / f"medisimplify-kb-{uuid.uuid4().hex}",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))
