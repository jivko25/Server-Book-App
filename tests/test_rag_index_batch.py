from unittest.mock import MagicMock, patch

import pytest

from app.services.rag_index import (
    RagBatchTooLargeError,
    _assign_global_chunk_indices,
    _estimate_passage_count,
    _validate_batch_size,
)
from app.services.rag_chunker import TextChunk


def test_estimate_passage_count_for_large_segment() -> None:
    chapters = [{"id": 1, "content": "a" * 70_000}]
    count = _estimate_passage_count(chapters)
    assert count >= 50


def test_validate_batch_size_rejects_huge_single_chapter() -> None:
    chapters = [{"id": 1, "content": "a" * 70_000}]
    with pytest.raises(RagBatchTooLargeError):
        _validate_batch_size(chapters)


def test_assign_global_chunk_indices_continues_from_db() -> None:
    chunks = [
        TextChunk(
            chapter_id=1,
            chapter_numeral=None,
            chapter_title=None,
            chunk_index=0,
            text="part two",
            start_char=0,
        ),
        TextChunk(
            chapter_id=1,
            chapter_numeral=None,
            chapter_title=None,
            chunk_index=1,
            text="part two b",
            start_char=100,
        ),
    ]
    chapters = [{"id": 1, "content": "x" * 1000, "contentOffset": 28_000}]

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"chapter_id": 1, "chunk_index": 17}]
    )

    with patch("app.services.rag_index.get_supabase_client", return_value=mock_client):
        adjusted = _assign_global_chunk_indices(
            book_id="book-1", chapters=chapters, chunks=chunks
        )

    assert [c.chunk_index for c in adjusted] == [18, 19]
    assert adjusted[0].start_char == 28_000
    assert adjusted[1].start_char == 28_100
