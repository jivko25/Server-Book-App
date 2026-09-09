from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chapter_id: int
    chapter_numeral: str | None
    chapter_title: str | None
    chunk_index: int
    text: str
    start_char: int


def chunk_chapter_text(
    content: str,
    *,
    chapter_id: int,
    chapter_numeral: str | None,
    chapter_title: str | None,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    normalized = content.strip()
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    chunk_index = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            split_at = normalized.rfind(" ", start, end)
            if split_at > start + chunk_size // 2:
                end = split_at

        text = normalized[start:end].strip()
        if text:
            chunks.append(
                TextChunk(
                    chapter_id=chapter_id,
                    chapter_numeral=chapter_numeral,
                    chapter_title=chapter_title,
                    chunk_index=chunk_index,
                    text=text,
                    start_char=start,
                )
            )
            chunk_index += 1

        if end >= len(normalized):
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def chunk_book(
    chapters: list[dict],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    all_chunks: list[TextChunk] = []
    for chapter in chapters:
        all_chunks.extend(
            chunk_chapter_text(
                chapter["content"],
                chapter_id=chapter["id"],
                chapter_numeral=chapter.get("numeral"),
                chapter_title=chapter.get("title"),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return all_chunks
