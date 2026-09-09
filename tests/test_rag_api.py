from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_rag_index_endpoint() -> None:
    mock_result = {
        "bookId": "book-1",
        "title": "Hamlet",
        "passageCount": 3,
        "status": "ready",
    }

    with (
        patch("app.routers.rag.check_supabase_connection", return_value=("ok", None)),
        patch("app.routers.rag.index_book", return_value=mock_result),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/index",
                json={
                    "bookId": "book-1",
                    "title": "Hamlet",
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
    assert body["status"] == "ready"
    assert body["passageCount"] == 3
