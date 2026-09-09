from pathlib import Path

import pytest

from app.services.rulit_parser import (
    RulitParseError,
    extract_book_id,
    parse_book_detail_page,
    parse_download_landing_page,
    parse_list_page,
    slugify_filename,
)

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://www.rulit.me"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_extract_book_id_from_page_url() -> None:
    url = "https://www.rulit.me/books/vranovata-rana-download-1138255.html"
    assert extract_book_id(url) == "1138255"


def test_parse_catalog_fixture() -> None:
    parsed = parse_list_page(
        _read("rulit_catalog.html"),
        base_url=BASE_URL,
        page=1,
        default_format="epub",
    )
    assert parsed["page"] == 1
    assert parsed["hasNext"] is True
    assert len(parsed["items"]) == 1
    item = parsed["items"][0]
    assert item["id"] == "1138255"
    assert item["title"] == "Врановата рана"
    assert item["author"] == "Макдоналд Ед"
    assert item["language"] == "bg"
    assert item["formats"] == ["epub"]


def test_parse_book_detail_fixture() -> None:
    parsed = parse_book_detail_page(
        _read("rulit_book_detail.html"),
        base_url=BASE_URL,
        book_id="319132",
    )
    assert parsed["id"] == "319132"
    assert parsed["title"] == "За спасяването на света"
    assert parsed["authors"] == ["Чолаков Янчо", "Дилов Любен"]
    assert parsed["year"] == "2014"
    assert parsed["genre"] == "Научная фантастика"
    assert parsed["rating"] == 4.5
    assert parsed["epubSizeKb"] == 2521
    assert parsed["download"]["epub"]["url"].endswith("download-books-319132.html?t=epub")


def test_parse_download_landing_fixture() -> None:
    page_url = parse_download_landing_page(
        _read("rulit_download_landing.html"),
        base_url=BASE_URL,
        book_id="319132",
    )
    assert page_url == "https://www.rulit.me/books/za-spasyavaneto-na-sveta-download-319132.html"


def test_slugify_filename() -> None:
    assert slugify_filename("За спасяването на света", "epub").endswith(".epub")


def test_parse_invalid_html_raises() -> None:
    with pytest.raises(RulitParseError):
        parse_list_page("<html><body>broken</body></html>", base_url=BASE_URL, page=1, default_format="epub")
