from fastapi import APIRouter, HTTPException

from app.schemas import ErrorResponse
from app.schemas_rag import (
    RagIndexRequest,
    RagIndexResponse,
    RagIndexStatusResponse,
)
from app.services.gemini import (
    GeminiAuthError,
    GeminiConfigurationError,
    GeminiQuotaError,
    GeminiUpstreamError,
)
from app.services.rag_index import (
    RagBookTooLargeError,
    RagIndexFailedError,
    get_index_status,
    index_book,
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
    _ensure_supabase()

    chapters = [
        {
            "id": chapter.id,
            "numeral": chapter.numeral,
            "title": chapter.title,
            "content": chapter.content,
        }
        for chapter in body.chapters
    ]

    try:
        result = index_book(book_id=body.bookId, title=body.title, chapters=chapters)
    except RagBookTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except GeminiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiQuotaError as exc:
        raise HTTPException(
            status_code=429,
            detail="Gemini API quota exceeded. Please try again later.",
        ) from exc
    except GeminiAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail="Invalid or unauthorized Gemini API key.",
        ) from exc
    except (GeminiUpstreamError, RagIndexFailedError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to index book for RAG chat.",
        ) from exc

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
