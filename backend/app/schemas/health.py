from typing import Literal

from pydantic import BaseModel

from app.schemas.evidence import KnowledgeBaseStatus


class LLMStatus(BaseModel):
    provider: Literal["gemini"] = "gemini"
    model: str
    api_key_configured: bool


class Limits(BaseModel):
    max_upload_mb: int
    max_pdf_pages: int


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str
    llm: LLMStatus
    limits: Limits
    knowledge_base: KnowledgeBaseStatus
