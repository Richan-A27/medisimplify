"""Application configuration loaded from environment variables.

Values come from the process environment first, then from a `.env` file at the
repository root (or `backend/.env`). Secrets are never logged or returned by the API.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MediSimplify"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM (Gemini). The key is optional so the app runs without it; LLM features
    # report a clear "not configured" state instead of failing at startup.
    gemini_api_key: SecretStr | None = None
    # Stable Flash-Lite model: free tier with the highest free daily limits of the current text models, and
    # fast enough for the 60 s timeout (gemini-3.8-flash timed out on the RAG prompt). Checked 2026-10-27.
    gemini_model: str = "gemini-3.5-flash-lite"
    # Fixed generation settings so prompting strategies are compared under identical conditions.
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_seed: int = 42
    llm_max_output_tokens: int = Field(default=8192, ge=256, le=65536)
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0)

    # Upload limits.
    max_upload_mb: int = Field(default=10, ge=1, le=50)
    max_pdf_pages: int = Field(default=30, ge=1, le=200)

    # Retrieval-augmented generation (local; no paid service required).
    knowledge_base_dir: Path = REPO_ROOT / "knowledge_base"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_max_words: int = Field(default=160, ge=40, le=1000)
    chunk_overlap_words: int = Field(default=40, ge=0, le=300)
    rag_top_k: int = Field(default=3, ge=1, le=10)
    # Calibrated on the bundled corpus (see README): relevant tests score >= 0.66, unrelated <= 0.54.
    rag_min_similarity: float = Field(default=0.60, ge=0.0, le=1.0)

    @property
    def index_dir(self) -> Path:
        return self.knowledge_base_dir / "index"

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def llm_configured(self) -> bool:
        return self.gemini_api_key is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
