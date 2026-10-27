from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.schemas.health import HealthResponse, Limits, LLMStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Liveness check plus non-secret configuration flags the frontend can display."""
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        llm=LLMStatus(model=settings.gemini_model, api_key_configured=settings.llm_configured),
        limits=Limits(max_upload_mb=settings.max_upload_mb, max_pdf_pages=settings.max_pdf_pages),
        knowledge_base=await run_in_threadpool(request.app.state.knowledge_base.status),
    )
