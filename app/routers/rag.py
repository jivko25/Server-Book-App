from fastapi import APIRouter, HTTPException

from app.schemas import ErrorResponse
from app.schemas_rag import (
    RagIndexBatchRequest,
    RagIndexBatchResponse,
    RagIndexRequest,
    RagIndexResponse,
    RagIndexStartRequest,
    RagIndexStartResponse,
    RagIndexStatusResponse,
)
from app.services.gemini import (
    GeminiAuthError,
    GeminiConfigurationError,
    GeminiQuotaError,
    GeminiUpstreamError,
)
from app.services.rag_index import (
    RagBatchTooLargeError,
    RagIndexFailedError,
    RagIndexNotFoundError,
    complete_index,
    get_index_status,
    index_batch,
    index_book,
    start_index,
)
from app.services.supabase_client import check_supabase_connection

router = APIRouter(prefix="/rag", tags=["rag"])


def _ensure_supabase() -> None:
    status, detail = check_supabase_connection()
    if status == "not_configured":
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if status == "error":
        raise HTTPException(
            status_code=502,
            detail=detail or "Supabase connection failed",
        )


def _map_gemini_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, GeminiConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, GeminiQuotaError):
        return HTTPException(
            status_code=429,
            detail="Gemini API quota exceeded. Please try again later.",
        )
    if isinstance(exc, GeminiAuthError):
        return HTTPException(
            status_code=exc.status_code,
            detail="Invalid or unauthorized Gemini API key.",
        )
    if isinstance(exc, (GeminiUpstreamError, RagIndexFailedError)):
        return HTTPException(status_code=502, detail="Failed to index book for RAG chat.")
    if isinstance(exc, RagBatchTooLargeError):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, RagIndexNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    raise exc


def _chapter_payload(chapters: list) -> list[dict]:
    return [
        {
            "id": chapter.id,
            "numeral": chapter.numeral,
            "title": chapter.title,
            "content": chapter.content,
        }
        for chapter in chapters
    ]


@router.post(
    "/index/start",
    response_model=RagIndexStartResponse,
    responses={502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def create_index_start(body: RagIndexStartRequest) -> RagIndexStartResponse:
    _ensure_supabase()
    try:
        result = start_index(book_id=body.bookId, title=body.title)
    except Exception as exc:
        raise _map_gemini_errors(exc) from exc
    return RagIndexStartResponse.model_validate(result)


@router.post(
    "/index/{book_id}/batch",
    response_model=RagIndexBatchResponse,
    responses={
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_index_batch(book_id: str, body: RagIndexBatchRequest) -> RagIndexBatchResponse:
    _ensure_supabase()
    try:
        result = index_batch(book_id=book_id, chapters=_chapter_payload(body.chapters))
    except Exception as exc:
        raise _map_gemini_errors(exc) from exc
    return RagIndexBatchResponse.model_validate(result)


@router.post(
    "/index/{book_id}/complete",
    response_model=RagIndexResponse,
    responses={
        404: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_index_complete(book_id: str) -> RagIndexResponse:
    _ensure_supabase()
    try:
        result = complete_index(book_id=book_id)
    except Exception as exc:
        raise _map_gemini_errors(exc) from exc
    return RagIndexResponse.model_validate(result)


@router.post(
    "/index",
    response_model=RagIndexResponse,
    responses={
        413: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_index(body: RagIndexRequest) -> RagIndexResponse:
    """Legacy single-shot index for small books."""

    _ensure_supabase()
    try:
        result = index_book(
            book_id=body.bookId,
            title=body.title,
            chapters=_chapter_payload(body.chapters),
        )
    except Exception as exc:
        raise _map_gemini_errors(exc) from exc
    return RagIndexResponse.model_validate(result)


@router.get(
    "/index/{book_id}",
    response_model=RagIndexStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def read_index_status(book_id: str) -> RagIndexStatusResponse:
    _ensure_supabase()
    status = get_index_status(book_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Book index not found")
    return RagIndexStatusResponse.model_validate(status)
