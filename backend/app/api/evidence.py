from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.rag.retrieval import KnowledgeBaseUnavailableError
from app.rag.service import KnowledgeBase
from app.schemas.errors import ErrorResponse
from app.schemas.evidence import EvidenceRequest, EvidenceResponse, KnowledgeBaseStatus

router = APIRouter(prefix="/evidence", tags=["evidence"])


def get_knowledge_base(request: Request) -> KnowledgeBase:
    return request.app.state.knowledge_base


@router.get("/status", response_model=KnowledgeBaseStatus)
async def status(request: Request) -> KnowledgeBaseStatus:
    return await run_in_threadpool(get_knowledge_base(request).status)


@router.post(
    "/retrieve",
    response_model=EvidenceResponse,
    responses={503: {"model": ErrorResponse}},
)
async def retrieve(
    body: EvidenceRequest, knowledge_base: Annotated[KnowledgeBase, Depends(get_knowledge_base)]
) -> EvidenceResponse | JSONResponse:
    """Retrieve general reference passages for test names. Send names only, never patient values."""
    try:
        retriever = knowledge_base.retriever()
        return await run_in_threadpool(retriever.retrieve_for_tests, body.test_names)
    except KnowledgeBaseUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(code=exc.code, message=str(exc) or exc.message).model_dump(),
        )
