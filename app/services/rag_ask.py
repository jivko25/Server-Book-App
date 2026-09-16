from __future__ import annotations

import logging

from google.genai import errors, types

from app.config import (
    GEMINI_MODEL,
    RAG_ASK_MATCH_COUNT,
    RAG_ASK_MATCH_POOL,
    RAG_ASK_MAX_OUTPUT_TOKENS,
    TEMPERATURE,
)
from app.services.gemini import (
    GeminiUpstreamError,
    _build_client,
    _build_thinking_config,
    _map_client_error,
)
from app.services.rag_embeddings import embed_query
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

RAG_ASK_SYSTEM = (
    "You are a literary assistant for FOLIO. Answer using ONLY the provided "
    "excerpts from the current audiobook chapter. If the excerpts do not contain "
    "enough information, say so briefly. Write in the same language as the user's "
    "question. Be concise (2–6 sentences). Do not invent plot points."
)

RAG_ASK_USER_TEMPLATE = """Book: {book_title}
Chapter: {chapter_label}

Excerpts:
{excerpt_block}

User question:
{question}
"""


class RagChapterNotIndexedError(Exception):
    """Raised when the chapter has no indexed passages."""


def _format_excerpt_block(rows: list[dict]) -> str:
    parts: list[str] = []
    for index, row in enumerate(rows, start=1):
        text = (row.get("text") or "").strip()
        if not text:
            continue
        parts.append(f"[{index}] {text}")
    return "\n\n".join(parts) if parts else ""


def _match_passages(
    *,
    book_id: str,
    chapter_id: int,
    query_embedding: list[float],
) -> list[dict]:
    client = get_supabase_client()
    result = client.rpc(
        "match_rag_passages",
        {
            "query_embedding": query_embedding,
            "match_book_id": book_id,
            "match_count": RAG_ASK_MATCH_POOL,
        },
    ).execute()

    rows = result.data or []
    chapter_rows = [row for row in rows if int(row.get("chapter_id", -1)) == chapter_id]
    chapter_rows.sort(key=lambda row: float(row.get("similarity") or 0), reverse=True)
    return chapter_rows[:RAG_ASK_MATCH_COUNT]


def _generate_answer(
    *,
    book_title: str,
    chapter_label: str,
    question: str,
    excerpts: list[dict],
) -> str:
    excerpt_block = _format_excerpt_block(excerpts)
    if not excerpt_block:
        raise GeminiUpstreamError("No excerpt text available for this chapter")

    prompt = RAG_ASK_USER_TEMPLATE.format(
        book_title=book_title,
        chapter_label=chapter_label,
        excerpt_block=excerpt_block,
        question=question.strip(),
    )

    client = _build_client()
    config = types.GenerateContentConfig(
        system_instruction=RAG_ASK_SYSTEM,
        temperature=TEMPERATURE,
        max_output_tokens=RAG_ASK_MAX_OUTPUT_TOKENS,
        thinking_config=_build_thinking_config(GEMINI_MODEL),
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
    except errors.ClientError as exc:
        raise _map_client_error(exc) from exc
    except Exception as exc:
        raise GeminiUpstreamError(str(exc)) from exc

    answer = (response.text or "").strip()
    if not answer:
        raise GeminiUpstreamError("Gemini returned an empty answer")
    return answer


def ask_chapter(
    *,
    book_id: str,
    chapter_id: int,
    question: str,
    book_title: str | None = None,
    chapter_title: str | None = None,
    chapter_numeral: str | None = None,
) -> dict:
    client = get_supabase_client()
    count_result = (
        client.table("rag_passages")
        .select("id", count="exact")
        .eq("book_id", book_id)
        .eq("chapter_id", chapter_id)
        .execute()
    )
    if (count_result.count or 0) == 0:
        raise RagChapterNotIndexedError(
            "This chapter is not indexed yet. Wait for chat preparation to finish."
        )

    query_embedding = embed_query(question)
    passages = _match_passages(
        book_id=book_id,
        chapter_id=chapter_id,
        query_embedding=query_embedding,
    )
    if not passages:
        raise RagChapterNotIndexedError("No matching passages found for this chapter.")

    label_parts = []
    if chapter_numeral:
        label_parts.append(f"Act {chapter_numeral}")
    if chapter_title:
        label_parts.append(chapter_title)
    chapter_label = " — ".join(label_parts) if label_parts else f"Chapter {chapter_id}"

    answer = _generate_answer(
        book_title=book_title or book_id,
        chapter_label=chapter_label,
        question=question,
        excerpts=passages,
    )

    citations = [
        {
            "chunkIndex": int(row.get("chunk_index", 0)),
            "text": (row.get("text") or "")[:280],
            "similarity": float(row.get("similarity") or 0),
        }
        for row in passages
    ]

    return {
        "bookId": book_id,
        "chapterId": chapter_id,
        "question": question.strip(),
        "answer": answer,
        "citations": citations,
    }
