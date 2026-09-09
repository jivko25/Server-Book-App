from app.services.rag_chunker import chunk_book


def test_chunk_book_splits_long_chapter() -> None:
    content = " ".join(["word"] * 400)
    chunks = chunk_book(
        [{"id": 1, "numeral": "I", "title": "Start", "content": content}],
        chunk_size=800,
        chunk_overlap=100,
    )
    assert len(chunks) >= 2
    assert chunks[0].chapter_id == 1
    assert chunks[0].chunk_index == 0


def test_chunk_book_skips_empty_chapter() -> None:
    chunks = chunk_book(
        [
            {"id": 1, "numeral": "I", "title": "Empty", "content": "   "},
            {"id": 2, "numeral": "II", "title": "Filled", "content": "Hello world"},
        ],
        chunk_size=800,
        chunk_overlap=100,
    )
    assert len(chunks) == 1
    assert chunks[0].chapter_id == 2
