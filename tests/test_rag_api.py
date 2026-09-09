from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_rag_index_start_endpoint() -> None:
    mock_result = {"bookId": "book-1", "title": "Hamlet", "status": "indexing"}

    with (
        patch("app.routers.rag.check_supabase_connection", return_value=("ok", None)),
        patch("app.routers.rag.start_index", return_value=mock_result),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/index/start",
                json={"bookId": "book-1", "title": "Hamlet"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "indexing"


@pytest.mark.anyio
async def test_rag_index_batch_endpoint() -> None:
    mock_result = {
        "bookId": "book-1",
        "batchPassageCount": 3,
        "totalPassageCount": 10,
        "status": "indexing",
    }

    with (
        patch("app.routers.rag.check_supabase_connection", return_value=("ok", None)),
        patch("app.routers.rag.index_batch", return_value=mock_result),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/index/book-1/batch",
                json={
                    "chapters": [
                        {
                            "id": 1,
                            "numeral": "I",
                            "title": "Scene 1",
                            "content": "The ghost appeared on the battlements at Elsinore.",
                        }
                    ],
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["batchPassageCount"] == 3
    assert body["totalPassageCount"] == 10


@pytest.mark.anyio
async def test_rag_index_complete_endpoint() -> None:
    mock_result = {
        "bookId": "book-1",
        "title": "Hamlet",
        "passageCount": 10,
        "status": "ready",
    }

    with (
        patch("app.routers.rag.check_supabase_connection", return_value=("ok", None)),
        patch("app.routers.rag.complete_index", return_value=mock_result),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/rag/index/book-1/complete")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
