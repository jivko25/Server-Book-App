from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from app.config import (
    RULIT_BASE_URL,
    RULIT_CACHE_TTL_SECONDS,
    RULIT_REQUEST_TIMEOUT_SECONDS,
    RULIT_USER_AGENT,
)
from app.services.cache import TTLCache
from app.services.rulit_parser import (
    RulitParseError,
    parse_book_detail_page,
    parse_download_landing_page,
    parse_list_page,
    slugify_filename,
)

logger = logging.getLogger(__name__)

_cache = TTLCache(ttl_seconds=RULIT_CACHE_TTL_SECONDS)


class RulitNotFoundError(Exception):
    """Raised when a book ID does not exist on rulit."""


class RulitUpstreamError(Exception):
    """Raised when rulit is unreachable or returns unexpected content."""


def _cache_key(prefix: str, *parts: str | int) -> str:
    return prefix + ":" + ":".join(str(part) for part in parts)


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": RULIT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
    }


def build_catalog_url(
    *,
    lang: str,
    page: int,
    sort: str,
    genre: str | None,
    fmt: str,
) -> str:
    if genre:
        return f"{RULIT_BASE_URL}/genre/{genre}/{lang}/{page}/{sort}?format={fmt}"
    return f"{RULIT_BASE_URL}/books/{lang}/{page}/{sort}?format={fmt}"


def build_search_url(*, lang: str, page: int, query: str, fmt: str = "epub") -> str:
    encoded = quote(query)
    return f"{RULIT_BASE_URL}/books/{lang}/{page}/date?format={fmt}&search={encoded}"


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.TimeoutException as exc:
        logger.error("Rulit request timed out: %s", url)
        raise RulitUpstreamError("Rulit request timed out") from exc
    except httpx.HTTPError as exc:
        logger.error("Rulit request failed: %s (%s)", url, exc)
        raise RulitUpstreamError("Rulit is temporarily unavailable") from exc

    if response.status_code == 404:
        raise RulitNotFoundError("Book not found")
    if response.status_code >= 400:
        logger.error("Rulit returned HTTP %s for %s", response.status_code, url)
        raise RulitUpstreamError("Rulit returned an unexpected response")

    text = response.text
    if "Страница не найдена" in text and "-download-" not in text:
        raise RulitNotFoundError("Book not found")
    return text


async def fetch_catalog(
    *,
    lang: str = "bg",
    page: int = 1,
    sort: str = "date",
    genre: str | None = None,
    fmt: str = "epub",
) -> dict:
    cache_key = _cache_key("catalog", lang, page, sort, genre or "-", fmt)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    url = build_catalog_url(lang=lang, page=page, sort=sort, genre=genre, fmt=fmt)
    async with httpx.AsyncClient(
        headers=_build_headers(),
        timeout=RULIT_REQUEST_TIMEOUT_SECONDS,
    ) as client:
        html = await _fetch_html(client, url)

    try:
        parsed = parse_list_page(html, base_url=RULIT_BASE_URL, page=page, default_format=fmt)
    except RulitParseError as exc:
        logger.exception("Failed to parse rulit catalog page")
        raise RulitUpstreamError(str(exc)) from exc

    for item in parsed["items"]:
        _cache.set(_cache_key("book_page", item["id"]), item["pageUrl"])

    _cache.set(cache_key, parsed)
    return parsed


async def search_books(
    *,
    query: str,
    lang: str = "bg",
    page: int = 1,
    fmt: str = "epub",
) -> dict:
    cache_key = _cache_key("search", lang, page, query.lower(), fmt)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    url = build_search_url(lang=lang, page=page, query=query, fmt=fmt)
    async with httpx.AsyncClient(
        headers=_build_headers(),
        timeout=RULIT_REQUEST_TIMEOUT_SECONDS,
    ) as client:
        html = await _fetch_html(client, url)

    try:
        parsed = parse_list_page(html, base_url=RULIT_BASE_URL, page=page, default_format=fmt)
    except RulitParseError as exc:
        logger.exception("Failed to parse rulit search page")
        raise RulitUpstreamError(str(exc)) from exc

    for item in parsed["items"]:
        _cache.set(_cache_key("book_page", item["id"]), item["pageUrl"])

    _cache.set(cache_key, parsed)
    return parsed


async def _resolve_book_page_url(client: httpx.AsyncClient, book_id: str) -> str:
    cached = _cache.get(_cache_key("book_page", book_id))
    if cached:
        return cached

    landing_url = f"{RULIT_BASE_URL}/download-books-{book_id}.html"
    html = await _fetch_html(client, landing_url)
    page_url = parse_download_landing_page(html, base_url=RULIT_BASE_URL, book_id=book_id)
    if not page_url:
        raise RulitUpstreamError("Failed to resolve rulit book page URL")

    _cache.set(_cache_key("book_page", book_id), page_url)
    return page_url


async def fetch_book_detail(book_id: str) -> dict:
    cache_key = _cache_key("book_detail", book_id)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(
        headers=_build_headers(),
        timeout=RULIT_REQUEST_TIMEOUT_SECONDS,
    ) as client:
        page_url = await _resolve_book_page_url(client, book_id)
        html = await _fetch_html(client, page_url)

    try:
        parsed = parse_book_detail_page(html, base_url=RULIT_BASE_URL, book_id=book_id)
    except RulitParseError as exc:
        logger.exception("Failed to parse rulit book detail for %s", book_id)
        raise RulitUpstreamError(str(exc)) from exc

    _cache.set(_cache_key("book_page", book_id), parsed["pageUrl"])
    _cache.set(cache_key, parsed)
    return parsed


async def fetch_download_url(
    book_id: str,
    *,
    fmt: str = "epub",
    resolve_redirect: bool = False,
) -> dict:
    cache_key = _cache_key("download_url", book_id, fmt, resolve_redirect)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{RULIT_BASE_URL}/download-books-{book_id}.html?t={fmt}"
    file_name = slugify_filename(f"book-{book_id}", fmt)
    resolved_url = None

    async with httpx.AsyncClient(
        headers=_build_headers(),
        timeout=RULIT_REQUEST_TIMEOUT_SECONDS,
    ) as client:
        try:
            detail = await fetch_book_detail(book_id)
            file_name = slugify_filename(detail["title"], fmt)
        except RulitNotFoundError:
            raise
        except RulitUpstreamError:
            detail = None

        if resolve_redirect:
            try:
                response = await client.head(url, follow_redirects=True)
                if response.status_code < 400 and str(response.url) != url:
                    resolved_url = str(response.url)
            except httpx.HTTPError as exc:
                logger.warning("Could not resolve rulit redirect for %s: %s", book_id, exc)

    payload = {
        "bookId": book_id,
        "format": fmt,
        "url": url,
        "fileName": file_name,
        "resolvedUrl": resolved_url,
    }
    _cache.set(cache_key, payload)
    return payload
