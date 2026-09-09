from __future__ import annotations

from google.genai import errors, types

from app.config import GEMINI_EMBEDDING_MODEL, RAG_EMBED_BATCH_SIZE
from app.services.gemini import (
    GeminiUpstreamError,
    _build_client,
    _map_client_error,
)

EMBED_DIMENSIONS = 768


def embed_passages(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    client = _build_client()
    all_vectors: list[list[float]] = []

    for offset in range(0, len(texts), RAG_EMBED_BATCH_SIZE):
        batch = texts[offset : offset + RAG_EMBED_BATCH_SIZE]
        config = types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_DIMENSIONS,
        )
        try:
            response = client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=batch,
                config=config,
            )
        except errors.ClientError as exc:
            raise _map_client_error(exc) from exc
        except Exception as exc:
            raise GeminiUpstreamError(str(exc)) from exc

        if not response.embeddings:
            raise GeminiUpstreamError("Gemini returned no embeddings")

        for embedding in response.embeddings:
            values = embedding.values or []
            if len(values) != EMBED_DIMENSIONS:
                raise GeminiUpstreamError(
                    f"Unexpected embedding size: {len(values)} (expected {EMBED_DIMENSIONS})"
                )
            all_vectors.append(list(values))

    if len(all_vectors) != len(texts):
        raise GeminiUpstreamError("Embedding count mismatch")

    return all_vectors
