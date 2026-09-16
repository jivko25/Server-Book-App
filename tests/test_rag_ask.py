from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_rag_ask_endpoint() -> None:
    mock_result = {
        "bookId": "book-1",
        "chapterId": 3,
        "question": "Who appears?",
        "answer": "The messenger arrives at dawn.",
        "citations": [
            {"chunkIndex": 0, "text": "At dawn...", "similarity": 0.82},
        ],
    }

    with (
        patch("app.routers.rag.check_supabase_connection", return_value=("ok", None)),
        patch("app.routers.rag.ask_chapter", return_value=mock_result),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/rag/ask",
                json={
                    "bookId": "book-1",
                    "chapterId": 3,
                    "question": "Who appears?",
                    "bookTitle": "Hamlet",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The messenger arrives at dawn."
    assert body["citations"][0]["chunkIndex"] == 0
