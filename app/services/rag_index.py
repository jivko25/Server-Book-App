from __future__ import annotations

import logging

from app.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE, RAG_MAX_BOOK_CHARS
from app.services.gemini import (
    GeminiAuthError,
    GeminiConfigurationError,
    GeminiQuotaError,
    GeminiUpstreamError,
)
from app.services.rag_chunker import TextChunk, chunk_book
from app.services.rag_embeddings import embed_passages
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

INSERT_BATCH_SIZE = 100


class RagIndexError(Exception):
    """Base error for indexing failures."""


class RagBookTooLargeError(RagIndexError):
    """Raised when book text exceeds configured limits."""


class RagIndexFailedError(RagIndexError):
    def __init__(self, message: str, *, book_id: str) -> None:
        super().__init__(message)
        self.book_id = book_id


def _mark_book_failed(book_id: str, title: str, message: str) -> None:
    client = get_supabase_client()
    row = {
        "id": book_id,
        "title": title,
        "status": "failed",
        "passage_count": 0,
    }
    client.table("rag_books").upsert(row).execute()
    logger.error("RAG index failed for %s: %s", book_id, message[:500])


def _set_book_indexing(book_id: str, title: str) -> None:
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


def _insert_passages(book_id: str, chunks: list[TextChunk], vectors: list[list[float]]) -> None:
    client = get_supabase_client()
    rows = [
        {
            "book_id": book_id,
            "chapter_id": chunk.chapter_id,
            "chapter_numeral": chunk.chapter_numeral,
            "chapter_title": chunk.chapter_title,
            "text": chunk.text,
            "start_char": chunk.start_char,
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    for offset in range(0, len(rows), INSERT_BATCH_SIZE):
        batch = rows[offset : offset + INSERT_BATCH_SIZE]
        client.table("rag_passages").insert(batch).execute()


def _mark_book_ready(book_id: str, title: str, passage_count: int) -> None:
    client = get_supabase_client()
    client.table("rag_books").upsert(
        {
            "id": book_id,
            "title": title,
            "status": "ready",
            "passage_count": passage_count,
        }
    ).execute()


def get_index_status(book_id: str) -> dict | None:
    client = get_supabase_client()
    result = client.table("rag_books").select("*").eq("id", book_id).limit(1).execute()
    rows = result.data or []
    if not rows:
        return None
    row = rows[0]
    return {
        "bookId": row["id"],
        "title": row["title"],
        "passageCount": row.get("passage_count", 0),
        "status": row.get("status", "indexing"),
        "errorMessage": row.get("error_message"),
    }


def index_book(*, book_id: str, title: str, chapters: list[dict]) -> dict:
    total_chars = sum(len(chapter["content"]) for chapter in chapters)
    if total_chars > RAG_MAX_BOOK_CHARS:
        raise RagBookTooLargeError(
            f"Book exceeds max size of {RAG_MAX_BOOK_CHARS} characters"
        )

    _set_book_indexing(book_id, title)

    try:
        chunks = chunk_book(
            chapters,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        if not chunks:
            raise RagIndexFailedError("No text chunks produced", book_id=book_id)

        vectors = embed_passages([chunk.text for chunk in chunks])
        _insert_passages(book_id, chunks, vectors)
        _mark_book_ready(book_id, title, len(chunks))

        return {
            "bookId": book_id,
            "title": title,
            "passageCount": len(chunks),
            "status": "ready",
        }
    except (
        GeminiConfigurationError,
        GeminiQuotaError,
        GeminiAuthError,
        GeminiUpstreamError,
        RagIndexFailedError,
        RagBookTooLargeError,
    ):
        raise
    except Exception as exc:
        logger.exception("RAG indexing failed for book %s", book_id)
        _mark_book_failed(book_id, title, str(exc))
        raise RagIndexFailedError(str(exc), book_id=book_id) from exc
