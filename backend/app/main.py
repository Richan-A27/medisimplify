"""FastAPI entry point: `uvicorn app.main:app --reload` from the backend directory."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.config import Settings, get_settings
from app.rag.service import KnowledgeBase
from app.schemas.errors import ErrorResponse

logger = logging.getLogger("medisimplify")


def _configure_logging(settings: Settings) -> None:
    # Logs record request metadata only. Report contents must never be logged.
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message).model_dump(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "Educational prototype that explains medical reports in plain language. "
            "Not a diagnostic tool and not a substitute for professional medical advice."
        ),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.knowledge_base = KnowledgeBase(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _error(exc.status_code, f"http_{exc.status_code}", message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations only; never echo submitted values back.
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
        return _error(422, "validation_error", f"Invalid request fields: {', '.join(fields)}")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
        return _error(500, "internal_error", "An unexpected error occurred. Please try again.")

    app.include_router(api_router)
    logger.info(
        "%s %s started (env=%s, llm_configured=%s)",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.llm_configured,
    )
    return app


app = create_app()
