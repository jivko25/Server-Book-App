from __future__ import annotations

import logging

from app.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_MAX_BATCH_CHARS
from app.services.rag_chunker import TextChunk, chunk_book
from app.services.rag_embeddings import EmbedError, embed_passages
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

INSERT_BATCH_SIZE = 100


class RagIndexError(Exception):
    """Base error for indexing failures."""


class RagBatchTooLargeError(RagIndexError):
    """Raised when a single batch exceeds configured limits."""


class RagIndexNotFoundError(RagIndexError):
    """Raised when indexing was never started for a book."""


class RagIndexFailedError(RagIndexError):
    def __init__(self, message: str, *, book_id: str) -> None:
        super().__init__(message)
        self.book_id = book_id


def _batch_char_count(chapters: list[dict]) -> int:
    return sum(len(chapter["content"]) for chapter in chapters)


def _validate_batch_size(chapters: list[dict]) -> None:
    if _batch_char_count(chapters) > RAG_MAX_BATCH_CHARS:
        raise RagBatchTooLargeError(
            f"Batch exceeds max size of {RAG_MAX_BATCH_CHARS} characters. "
            "Send fewer or shorter chapters per batch."
        )


def _mark_book_failed(book_id: str, title: str, message: str) -> None:
    client = get_supabase_client()
    client.table("rag_books").upsert(
        {
            "id": book_id,
            "title": title,
            "status": "failed",
            "passage_count": 0,
        }
    ).execute()
    logger.error("RAG index failed for %s: %s", book_id, message[:500])


def _count_passages(book_id: str) -> int:
    client = get_supabase_client()
    result = (
        client.table("rag_passages")
        .select("id", count="exact")
        .eq("book_id", book_id)
        .execute()
    )
    return result.count or 0


def _get_book_row(book_id: str) -> dict | None:
    client = get_supabase_client()
    result = client.table("rag_books").select("*").eq("id", book_id).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None


def _insert_passages(book_id: str, chunks: list[TextChunk], vectors: list[list[float]]) -> None:
    client = get_supabase_client()
    rows = [
        {
            "book_id": book_id,
            "chapter_id": chunk.chapter_id,
            "chapter_numeral": chunk.chapter_numeral,
            "chapter_title": chunk.chapter_title,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "start_char": chunk.start_char,
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    for offset in range(0, len(rows), INSERT_BATCH_SIZE):
        batch = rows[offset : offset + INSERT_BATCH_SIZE]
        client.table("rag_passages").insert(batch).execute()


def _update_passage_count(book_id: str, passage_count: int) -> None:
    client = get_supabase_client()
    client.table("rag_books").update({"passage_count": passage_count}).eq(
        "id", book_id
    ).execute()


def start_index(*, book_id: str, title: str) -> dict:
    client = get_supabase_client()
    client.table("rag_books").upsert(
        {
            "id": book_id,
            "title": title,
            "status": "indexing",
            "passage_count": 0,
        }
    ).execute()
    client.table("rag_passages").delete().eq("book_id", book_id).execute()
    return {"bookId": book_id, "title": title, "status": "indexing"}


def index_batch(*, book_id: str, chapters: list[dict]) -> dict:
    _validate_batch_size(chapters)

    book = _get_book_row(book_id)
    if book is None:
        raise RagIndexNotFoundError("Book index not found. Call /index/start first.")
    if book.get("status") not in ("indexing", "ready"):
        raise RagIndexFailedError(
            f"Book index is {book.get('status')}", book_id=book_id
        )

    title = book["title"]
    try:
        chunks = chunk_book(
            chapters,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        if not chunks:
            return {
                "bookId": book_id,
                "batchPassageCount": 0,
                "totalPassageCount": _count_passages(book_id),
                "status": "indexing",
            }

        vectors = embed_passages([chunk.text for chunk in chunks])
        _insert_passages(book_id, chunks, vectors)

        total = _count_passages(book_id)
        _update_passage_count(book_id, total)

        return {
            "bookId": book_id,
            "batchPassageCount": len(chunks),
            "totalPassageCount": total,
            "status": "indexing",
        }
    except (EmbedError, RagBatchTooLargeError):
        raise
    except Exception as exc:
        logger.exception("RAG batch indexing failed for book %s", book_id)
        _mark_book_failed(book_id, title, str(exc))
        raise RagIndexFailedError(str(exc), book_id=book_id) from exc


def complete_index(*, book_id: str) -> dict:
    book = _get_book_row(book_id)
    if book is None:
        raise RagIndexNotFoundError("Book index not found. Call /index/start first.")

    title = book["title"]
    total = _count_passages(book_id)
    if total == 0:
        _mark_book_failed(book_id, title, "No passages indexed")
        raise RagIndexFailedError("No passages indexed", book_id=book_id)

    client = get_supabase_client()
    client.table("rag_books").upsert(
        {
            "id": book_id,
            "title": title,
            "status": "ready",
            "passage_count": total,
        }
    ).execute()

    return {
        "bookId": book_id,
        "title": title,
        "passageCount": total,
        "status": "ready",
    }


def get_index_status(book_id: str) -> dict | None:
    row = _get_book_row(book_id)
    if row is None:
        return None
    return {
        "bookId": row["id"],
        "title": row["title"],
        "passageCount": row.get("passage_count", 0),
        "status": row.get("status", "indexing"),
        "errorMessage": row.get("error_message"),
    }


def index_book(*, book_id: str, title: str, chapters: list[dict]) -> dict:
    """Legacy single-shot index — delegates to batch flow."""

    start_index(book_id=book_id, title=title)

    batch_size = 5
    for offset in range(0, len(chapters), batch_size):
        batch = chapters[offset : offset + batch_size]
        index_batch(book_id=book_id, chapters=batch)

    return complete_index(book_id=book_id)
