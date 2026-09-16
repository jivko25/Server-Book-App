from __future__ import annotations

import logging
from dataclasses import replace

from app.config import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_MAX_BATCH_CHARS,
    RAG_MAX_PASSAGES_PER_BATCH,
)
from app.services.rag_chunker import TextChunk, chunk_book
from app.services.gemini import (
    GeminiAuthError,
    GeminiConfigurationError,
    GeminiQuotaError,
    GeminiUpstreamError,
)
from app.services.rag_embeddings import embed_passages
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


def _estimate_passage_count(chapters: list[dict]) -> int:
    stride = max(1, RAG_CHUNK_SIZE - RAG_CHUNK_OVERLAP)
    total = 0
    for chapter in chapters:
        length = len(chapter["content"].strip())
        if length:
            total += max(1, (length + stride - 1) // stride)
    return total


def _validate_batch_size(chapters: list[dict]) -> None:
    if _batch_char_count(chapters) > RAG_MAX_BATCH_CHARS:
        raise RagBatchTooLargeError(
            f"Batch exceeds max size of {RAG_MAX_BATCH_CHARS} characters. "
            "Send fewer or shorter chapters per batch."
        )
    estimated = _estimate_passage_count(chapters)
    if estimated > RAG_MAX_PASSAGES_PER_BATCH:
        raise RagBatchTooLargeError(
            f"Batch would create ~{estimated} passages; "
            f"max is {RAG_MAX_PASSAGES_PER_BATCH} per request."
        )


def _max_chunk_index_by_chapter(book_id: str, chapter_ids: set[int]) -> dict[int, int]:
    if not chapter_ids:
        return {}
    client = get_supabase_client()
    result = (
        client.table("rag_passages")
        .select("chapter_id, chunk_index")
        .eq("book_id", book_id)
        .in_("chapter_id", list(chapter_ids))
        .execute()
    )
    max_by: dict[int, int] = {}
    for row in result.data or []:
        chapter_id = int(row["chapter_id"])
        chunk_index = int(row["chunk_index"])
        max_by[chapter_id] = max(max_by.get(chapter_id, -1), chunk_index)
    return max_by


def _assign_global_chunk_indices(
    *,
    book_id: str,
    chapters: list[dict],
    chunks: list[TextChunk],
) -> list[TextChunk]:
    if not chunks:
        return []

    offsets = {int(ch["id"]): int(ch.get("contentOffset") or 0) for ch in chapters}
    max_indices = _max_chunk_index_by_chapter(
        book_id, {chunk.chapter_id for chunk in chunks}
    )

    by_chapter: dict[int, list[TextChunk]] = {}
    for chunk in chunks:
        by_chapter.setdefault(chunk.chapter_id, []).append(chunk)

    adjusted: list[TextChunk] = []
    for chapter_id, chapter_chunks in by_chapter.items():
        chapter_chunks.sort(
            key=lambda c: (offsets.get(chapter_id, 0) + c.start_char, c.chunk_index)
        )
        base = max_indices.get(chapter_id, -1) + 1
        content_offset = offsets.get(chapter_id, 0)
        for index, chunk in enumerate(chapter_chunks):
            adjusted.append(
                replace(
                    chunk,
                    chunk_index=base + index,
                    start_char=content_offset + chunk.start_char,
                )
            )
    return adjusted


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


def _delete_chapter_passages(book_id: str, chapter_id: int) -> None:
    client = get_supabase_client()
    client.table("rag_passages").delete().eq("book_id", book_id).eq(
        "chapter_id", chapter_id
    ).execute()


def register_book(*, book_id: str, title: str) -> dict:
    """Register a book for incremental (per-chapter) indexing without wiping passages."""
    client = get_supabase_client()
    existing = _get_book_row(book_id)
    if existing is None:
        client.table("rag_books").insert(
            {
                "id": book_id,
                "title": title,
                "status": "indexing",
                "passage_count": 0,
            }
        ).execute()
        status = "indexing"
        passage_count = 0
    else:
        status = existing.get("status", "indexing")
        if status == "failed":
            status = "indexing"
        client.table("rag_books").update({"title": title, "status": status}).eq(
            "id", book_id
        ).execute()
        passage_count = existing.get("passage_count", 0)

    return {
        "bookId": book_id,
        "title": title,
        "status": status,
        "passageCount": passage_count,
    }


def get_chapter_index_status(*, book_id: str, chapter_id: int) -> dict:
    client = get_supabase_client()
    book = _get_book_row(book_id)
    if book is None:
        raise RagIndexNotFoundError("Book index not registered.")

    result = (
        client.table("rag_passages")
        .select("id", count="exact")
        .eq("book_id", book_id)
        .eq("chapter_id", chapter_id)
        .execute()
    )
    passage_count = result.count or 0
    return {
        "bookId": book_id,
        "chapterId": chapter_id,
        "passageCount": passage_count,
        "status": "ready" if passage_count > 0 else "missing",
    }


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
        for chapter in chapters:
            if int(chapter.get("contentOffset") or 0) == 0:
                _delete_chapter_passages(book_id, int(chapter["id"]))

        chunks = chunk_book(
            chapters,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        if len(chunks) > RAG_MAX_PASSAGES_PER_BATCH:
            raise RagBatchTooLargeError(
                f"Batch produced {len(chunks)} passages; "
                f"max is {RAG_MAX_PASSAGES_PER_BATCH} per request."
            )
        chunks = _assign_global_chunk_indices(
            book_id=book_id, chapters=chapters, chunks=chunks
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
    except (
        GeminiConfigurationError,
        GeminiQuotaError,
        GeminiAuthError,
        GeminiUpstreamError,
        RagBatchTooLargeError,
    ):
        raise
    except Exception as exc:
        logger.exception("RAG batch indexing failed for book %s", book_id)
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
