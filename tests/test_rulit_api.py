from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_catalog_endpoint_returns_items() -> None:
    mock_data = {
        "page": 1,
        "hasNext": True,
        "items": [
            {
                "id": "1138255",
                "title": "Врановата рана",
                "author": "Макдоналд Ед",
                "language": "bg",
                "year": None,
                "genre": "Роман, повесть",
                "rating": None,
                "coverUrl": "https://www.rulit.me/data/programs/images/vranovata-rana_1138255.jpg",
                "pageUrl": "https://www.rulit.me/books/vranovata-rana-download-1138255.html",
                "formats": ["epub"],
                "epubSizeKb": None,
            }
        ],
    }

    with patch("app.routers.rulit.fetch_catalog", new=AsyncMock(return_value=mock_data)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/rulit/catalog?page=1")

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["items"][0]["id"] == "1138255"


@pytest.mark.anyio
async def test_book_not_found_returns_404() -> None:
    from app.services.rulit_scraper import RulitNotFoundError

    with patch(
        "app.routers.rulit.fetch_book_detail",
        new=AsyncMock(side_effect=RulitNotFoundError("Book not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/rulit/books/999999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found"
