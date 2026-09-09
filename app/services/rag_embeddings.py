from __future__ import annotations

import logging
import re
import time

from google.genai import errors, types

from app.config import (
    GEMINI_EMBEDDING_MODEL,
    RAG_EMBED_BATCH_DELAY_SECONDS,
    RAG_EMBED_BATCH_SIZE,
    RAG_EMBED_RETRY_MAX,
)
from app.services.gemini import (
    GeminiUpstreamError,
    _build_client,
    _map_client_error,
)

logger = logging.getLogger(__name__)

EMBED_DIMENSIONS = 768
_RETRY_DELAY_PATTERN = re.compile(r"retry in ([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)


def _retry_delay_seconds(exc: errors.ClientError, attempt: int) -> float:
    message = str(exc)
    match = _RETRY_DELAY_PATTERN.search(message)
    if match:
        return float(match.group(1)) + 1.0
    return min(15.0 * attempt, 60.0)


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

        last_error: Exception | None = None
        for attempt in range(1, RAG_EMBED_RETRY_MAX + 1):
            try:
                response = client.models.embed_content(
                    model=GEMINI_EMBEDDING_MODEL,
                    contents=batch,
                    config=config,
                )
                last_error = None
                break
            except errors.ClientError as exc:
                mapped = _map_client_error(exc)
                if exc.code == 429 and attempt < RAG_EMBED_RETRY_MAX:
                    delay = _retry_delay_seconds(exc, attempt)
                    logger.warning(
                        "Gemini embed quota hit, retry %s/%s in %.0fs",
                        attempt,
                        RAG_EMBED_RETRY_MAX,
                        delay,
                    )
                    time.sleep(delay)
                    last_error = mapped
                    continue
                raise mapped from exc
            except Exception as exc:
                raise GeminiUpstreamError(str(exc)) from exc

        if last_error is not None:
            raise last_error

        if not response.embeddings:
            raise GeminiUpstreamError("Gemini returned no embeddings")

        for embedding in response.embeddings:
            values = embedding.values or []
            if len(values) != EMBED_DIMENSIONS:
                raise GeminiUpstreamError(
                    f"Unexpected embedding size: {len(values)} (expected {EMBED_DIMENSIONS})"
                )
            all_vectors.append(list(values))

        if offset + RAG_EMBED_BATCH_SIZE < len(texts) and RAG_EMBED_BATCH_DELAY_SECONDS > 0:
            time.sleep(RAG_EMBED_BATCH_DELAY_SECONDS)

    if len(all_vectors) != len(texts):
        raise GeminiUpstreamError("Embedding count mismatch")

    return all_vectors
