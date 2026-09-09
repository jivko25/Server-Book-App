from fastapi import APIRouter, HTTPException, Query

from app.schemas_rulit import (
    RulitBookDetail,
    RulitCatalogResponse,
    RulitDownloadUrlResponse,
)
from app.services.rulit_scraper import (
    RulitNotFoundError,
    RulitUpstreamError,
    fetch_book_detail,
    fetch_catalog,
    fetch_download_url,
    search_books,
)

router = APIRouter(prefix="/rulit", tags=["rulit"])


@router.get("/catalog", response_model=RulitCatalogResponse)
async def get_catalog(
    lang: str = Query(default="bg", min_length=2, max_length=5),
    page: int = Query(default=1, ge=1),
    sort: str = Query(default="date", pattern="^(date|popular)$"),
    genre: str | None = Query(default=None, max_length=100),
    format: str = Query(default="epub", alias="format", pattern="^epub$"),
) -> RulitCatalogResponse:
    try:
        data = await fetch_catalog(lang=lang, page=page, sort=sort, genre=genre, fmt=format)
    except RulitUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RulitCatalogResponse.model_validate(data)


@router.get("/search", response_model=RulitCatalogResponse)
async def search_catalog(
    q: str = Query(..., min_length=2, max_length=200),
    lang: str = Query(default="bg", min_length=2, max_length=5),
    page: int = Query(default=1, ge=1),
    format: str = Query(default="epub", alias="format", pattern="^epub$"),
) -> RulitCatalogResponse:
    try:
        data = await search_books(query=q, lang=lang, page=page, fmt=format)
    except RulitUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RulitCatalogResponse.model_validate(data)


@router.get("/books/{book_id}", response_model=RulitBookDetail)
async def get_book(book_id: str) -> RulitBookDetail:
    if not book_id.isdigit():
        raise HTTPException(status_code=422, detail="book_id must be numeric")

    try:
        data = await fetch_book_detail(book_id)
    except RulitNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except RulitUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RulitBookDetail.model_validate(data)


@router.get("/books/{book_id}/download-url", response_model=RulitDownloadUrlResponse)
async def get_download_url(
    book_id: str,
    format: str = Query(default="epub", alias="format", pattern="^epub$"),
    resolve: bool = Query(default=False, description="Resolve redirect to final file URL"),
) -> RulitDownloadUrlResponse:
    if not book_id.isdigit():
        raise HTTPException(status_code=422, detail="book_id must be numeric")

    try:
        data = await fetch_download_url(book_id, fmt=format, resolve_redirect=resolve)
    except RulitNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except RulitUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RulitDownloadUrlResponse.model_validate(data)
