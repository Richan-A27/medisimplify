from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.evidence import get_knowledge_base
from app.config import Settings, get_settings
from app.rag.retrieval import KnowledgeBaseUnavailableError
from app.rag.service import KnowledgeBase
from app.schemas.errors import ErrorResponse
from app.schemas.report import ExtractionResponse
from app.schemas.summary import Strategy, SummaryResponse
from app.services.llm import GeminiClient, GenerationSettings, LLMClient, LLMError, LLMNotConfiguredError
from app.services.pdf_extraction import (
    FileTooLargeError,
    NotAPDFError,
    PDFExtractionError,
    PyMuPDFTextExtractor,
    TextExtractor,
)
from app.services.report_extraction import extract_report
from app.services.summarizer import NoMeasurementsError, summarize

router = APIRouter(prefix="/reports", tags=["reports"])

ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
READ_CHUNK_BYTES = 1024 * 1024
ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (400, 413, 415, 422, 429, 502, 503, 504)}


def get_extractor(settings: Annotated[Settings, Depends(get_settings)]) -> TextExtractor:
    return PyMuPDFTextExtractor(max_pages=settings.max_pdf_pages)


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> LLMClient | None:
    """Returns None when no key is configured; the endpoint turns that into a clear 503."""
    if settings.gemini_api_key is None:
        return None
    return GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        settings=GenerationSettings(
            temperature=settings.llm_temperature,
            seed=settings.llm_seed,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ErrorResponse(code=code, message=message).model_dump())


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read at most `max_bytes`; stop early instead of buffering an oversized upload."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(READ_CHUNK_BYTES):
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"The file exceeds the {max_bytes // (1024 * 1024)} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


async def _extract(file: UploadFile, settings: Settings, extractor: TextExtractor) -> ExtractionResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise NotAPDFError()
    data = await _read_limited(file, settings.max_upload_bytes)
    return await run_in_threadpool(extract_report, data, extractor=extractor, max_bytes=settings.max_upload_bytes)


@router.post("/extract", response_model=ExtractionResponse, responses=ERROR_RESPONSES)
async def extract(
    file: Annotated[UploadFile, File(description="Digitally generated PDF lab report")],
    settings: Annotated[Settings, Depends(get_settings)],
    extractor: Annotated[TextExtractor, Depends(get_extractor)],
) -> ExtractionResponse | JSONResponse:
    """Extract text and candidate test results from a PDF. The file is processed in memory and not stored."""
    try:
        return await _extract(file, settings, extractor)
    except PDFExtractionError as exc:
        return _error(exc.status_code, exc.code, exc.message)
    finally:
        await file.close()


@router.post("/summarize", response_model=SummaryResponse, responses=ERROR_RESPONSES)
async def summarize_report(
    file: Annotated[UploadFile, File(description="Digitally generated PDF lab report")],
    settings: Annotated[Settings, Depends(get_settings)],
    extractor: Annotated[TextExtractor, Depends(get_extractor)],
    llm: Annotated[LLMClient | None, Depends(get_llm)],
    knowledge_base: Annotated[KnowledgeBase, Depends(get_knowledge_base)],
    strategy: Annotated[Strategy, Form()] = "rag",
) -> SummaryResponse | JSONResponse:
    """Extract the report again on the server, then generate and validate a plain-language summary.

    Only structured test results (and, for `rag`, general reference passages) are sent to the LLM.
    """
    try:
        extraction = await _extract(file, settings, extractor)
        if llm is None:
            raise LLMNotConfiguredError()
        return await run_in_threadpool(summarize, extraction, strategy, llm, knowledge_base.retriever)
    except (PDFExtractionError, LLMError, NoMeasurementsError) as exc:
        return _error(exc.status_code, exc.code, exc.message)
    except KnowledgeBaseUnavailableError as exc:
        return _error(503, exc.code, str(exc) or exc.message)
    finally:
        await file.close()
