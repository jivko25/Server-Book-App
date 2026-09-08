from fastapi import APIRouter, HTTPException

from app.schemas import ErrorResponse, SummaryRequest, SummaryResponse
from app.services.gemini import (
    GeminiAuthError,
    GeminiConfigurationError,
    GeminiQuotaError,
    GeminiUpstreamError,
    generate_chapter_summary,
)

router = APIRouter(prefix="/summary", tags=["summary"])


@router.post(
    "",
    response_model=SummaryResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Gemini API quota exceeded"},
        401: {"model": ErrorResponse, "description": "Invalid Gemini API key"},
        403: {"model": ErrorResponse, "description": "Gemini API access denied"},
        502: {"model": ErrorResponse, "description": "Upstream Gemini failure"},
        503: {"model": ErrorResponse, "description": "Server not configured"},
    },
)
def create_summary(body: SummaryRequest) -> SummaryResponse:
    try:
        summary = generate_chapter_summary(
            body.chapter_text,
            book_title=body.book_title,
            chapter_title=body.chapter_title,
            chapter_numeral=body.chapter_numeral,
        )
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
    except GeminiUpstreamError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini API is temporarily unavailable.",
        ) from exc

    return SummaryResponse(summary=summary)
