from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BOOK_ID_PATTERN = re.compile(r"-download-(\d+)\.html")
DOWNLOAD_BOOKS_PATTERN = re.compile(r"download-books-(\d+)\.html")
FORMAT_SIZE_PATTERN = re.compile(
    r"<strong>\s*([A-Z0-9]+)\s*</strong>\s*&nbsp;\((\d+)\s*Kb\)",
    re.IGNORECASE,
)
RATING_PATTERN = re.compile(
    r"Рейтинг:\s*<strong>\s*([\d.,]+)\s*</strong>\s*/\s*5",
    re.IGNORECASE,
)

LANGUAGE_MAP = {
    "болгарский": "bg",
    "русский": "ru",
    "английский": "en",
    "украинский": "uk",
}


class RulitParseError(Exception):
    """Raised when rulit HTML cannot be parsed."""


def extract_book_id(url: str) -> str | None:
    match = BOOK_ID_PATTERN.search(url) or DOWNLOAD_BOOKS_PATTERN.search(url)
    return match.group(1) if match else None


def normalize_language(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if len(cleaned) == 2:
        return cleaned
    return LANGUAGE_MAP.get(cleaned, cleaned)


def slugify_filename(title: str, extension: str = "epub") -> str:
    slug = title.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    if not slug:
        slug = "book"
    return f"{slug}.{extension}"


def _abs_url(base_url: str, href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(base_url + "/", href.lstrip("/"))


def _text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return " ".join(tag.stripped_strings)


def _parse_book_info_value(book_info: Tag) -> str:
    links = book_info.find_all("a")
    if links:
        return ", ".join(_text(link) for link in links)
    value = book_info.find("span", class_="date_value")
    if value is not None:
        return _text(value)
    text = book_info.get_text(" ", strip=True)
    for prefix in ("Автор:", "Язык:", "Год:", "Серия:"):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _parse_rating(html: str) -> float | None:
    match = RATING_PATTERN.search(html)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_formats_from_html(html: str) -> list[dict[str, int | str | None]]:
    formats: list[dict[str, int | str | None]] = []
    seen: set[str] = set()
    for match in FORMAT_SIZE_PATTERN.finditer(html):
        fmt = match.group(1).lower()
        if fmt in seen:
            continue
        seen.add(fmt)
        formats.append({"type": fmt, "sizeKb": int(match.group(2))})
    return formats


def parse_list_page(html: str, *, base_url: str, page: int, default_format: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    seen_ids: set[str] = set()

    for article in soup.select("article.single-blog.post-list"):
        if article.find_parent("aside") is not None:
            continue

        title_link = article.select_one("h4 a[href*='-download-']")
        if title_link is None:
            continue

        has_author = any(
            "Автор:" in info.get_text(" ", strip=True)
            for info in article.select("div.book_info")
        )
        has_cover = article.select_one(".media-left img") is not None
        if not has_author and not has_cover:
            continue

        page_url = _abs_url(base_url, title_link.get("href"))
        if not page_url:
            continue
        book_id = extract_book_id(page_url)
        if not book_id or book_id in seen_ids:
            continue
        seen_ids.add(book_id)

        title_tag = title_link.find("strong") or title_link
        title = _text(title_tag)

        author = ""
        genre = None
        language = None
        for info in article.select("div.book_info"):
            label = info.get_text(" ", strip=True)
            if label.startswith("Автор:"):
                author = _parse_book_info_value(info)
            elif label.startswith("Язык:"):
                language = normalize_language(_parse_book_info_value(info))
            elif info.find("a", class_="post-cat") is None and "Серия:" in label:
                continue

        genre_link = article.select_one("a.post-cat")
        if genre_link is not None:
            genre = _text(genre_link)

        cover_link = article.select_one(".media-left img")
        cover_url = _abs_url(base_url, cover_link.get("src")) if cover_link else None

        formats = [default_format] if default_format != "all" else []
        epub_size = None

        items.append(
            {
                "id": book_id,
                "title": title,
                "author": author,
                "language": language,
                "year": None,
                "genre": genre,
                "rating": None,
                "coverUrl": cover_url,
                "pageUrl": page_url.split("#")[0],
                "formats": formats,
                "epubSizeKb": epub_size,
            }
        )

    if not items:
        looks_like_list_page = any(
            marker in html
            for marker in (
                "single-blog post-list",
                "pagination",
                "Все книги",
                "SearchBook",
                "post-pagination",
            )
        )
        if not looks_like_list_page:
            logger.warning("Rulit list page structure may have changed — no items found")
            raise RulitParseError("Failed to parse rulit catalog page")

    has_next = _parse_has_next(soup, page) if items else False
    return {"page": page, "hasNext": has_next, "items": items}


def _parse_has_next(soup: BeautifulSoup, current_page: int) -> bool:
    for link in soup.select("ul.pagination a[href]"):
        href = link.get("href", "")
        title = link.get("title", "")
        text = link.get_text(strip=True)
        if title == "Следующая страница" or text in {"›", "»"}:
            return True
        match = re.search(r"/(\d+)/(?:date|popular|name|rating)", href)
        if match and int(match.group(1)) > current_page:
            return True
    return False


def parse_book_detail_page(html: str, *, base_url: str, book_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.select_one("h2")
    if title_tag is None:
        raise RulitParseError("Failed to parse rulit book detail page")

    title = _text(title_tag)
    authors: list[str] = []
    language = None
    year = None
    series = None
    genre = None

    genre_link = soup.select_one(".entry-header a.post-cat, .entry-content-view a.post-cat")
    if genre_link is not None:
        genre = _text(genre_link)

    for info in soup.select("div.book_info"):
        label = info.get_text(" ", strip=True)
        if label.startswith("Автор:"):
            authors = [
                _text(link) for link in info.find_all("a") if _text(link)
            ] or [_parse_book_info_value(info)]
        elif label.startswith("Язык:"):
            language = normalize_language(_parse_book_info_value(info))
        elif label.startswith("Год:"):
            year = _parse_book_info_value(info)
        elif label.startswith("Серия:"):
            series = _parse_book_info_value(info)

    cover_img = soup.select_one(".post-thumb img[alt]")
    cover_url = _abs_url(base_url, cover_img.get("src")) if cover_img else None

    canonical = soup.select_one('link[rel="canonical"]')
    page_url = canonical.get("href") if canonical else None
    if not page_url:
        page_url = f"{base_url}/books/book-download-{book_id}.html"

    synopsis = None
    annotation = soup.select_one("div.annotation p")
    if annotation is not None:
        synopsis = annotation.get_text("\n", strip=True)

    formats = _parse_formats_from_html(html)
    format_types = [item["type"] for item in formats if item.get("type")]
    epub_size = next(
        (item["sizeKb"] for item in formats if item.get("type") == "epub"),
        None,
    )

    rating = _parse_rating(html)
    download_url = f"{base_url}/download-books-{book_id}.html?t=epub"

    return {
        "id": book_id,
        "title": title,
        "author": authors[0] if authors else "",
        "authors": authors,
        "language": language,
        "year": year,
        "genre": genre,
        "series": series,
        "rating": rating,
        "coverUrl": cover_url,
        "pageUrl": page_url,
        "synopsis": synopsis,
        "formats": formats,
        "epubSizeKb": epub_size,
        "download": {
            "epub": {
                "url": download_url,
                "fileName": slugify_filename(title, "epub"),
            }
        },
    }


def parse_download_landing_page(html: str, *, base_url: str, book_id: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("ol.breadcrumb a[href*='-download-']"):
        href = link.get("href")
        if href and book_id in href:
            return _abs_url(base_url, href.split("#")[0])
    for link in soup.select("a[href*='-download-']"):
        href = link.get("href", "")
        if book_id in href:
            return _abs_url(base_url, href.split("#")[0])
    return None
