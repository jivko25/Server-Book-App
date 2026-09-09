from __future__ import annotations

import logging
import threading

from app.config import RAG_EMBED_BATCH_SIZE, RAG_LOCAL_EMBED_MODEL

logger = logging.getLogger(__name__)

EMBED_DIMENSIONS = 768

_model = None
_model_lock = threading.Lock()


class EmbedError(Exception):
    """Local embedding model failed."""


def _get_model():
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            from fastembed import TextEmbedding

            logger.info("Loading local embed model: %s", RAG_LOCAL_EMBED_MODEL)
            _model = TextEmbedding(model_name=RAG_LOCAL_EMBED_MODEL)
    return _model


def _prefix_passages(texts: list[str]) -> list[str]:
    """multilingual-e5 models expect a passage prefix for document indexing."""
    if "e5" not in RAG_LOCAL_EMBED_MODEL.lower():
        return texts

    prefixed: list[str] = []
    for text in texts:
        lowered = text.lower()
        if lowered.startswith("passage:") or lowered.startswith("query:"):
            prefixed.append(text)
        else:
            prefixed.append(f"passage: {text}")
    return prefixed


def embed_passages(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = _get_model()
    prefixed = _prefix_passages(texts)
    all_vectors: list[list[float]] = []

    for offset in range(0, len(prefixed), RAG_EMBED_BATCH_SIZE):
        batch = prefixed[offset : offset + RAG_EMBED_BATCH_SIZE]
        try:
            batch_vectors = list(model.embed(batch))
        except Exception as exc:
            raise EmbedError(str(exc)) from exc

        for vector in batch_vectors:
            values = [float(value) for value in vector]
            if len(values) != EMBED_DIMENSIONS:
                raise EmbedError(
                    f"Unexpected embedding size: {len(values)} (expected {EMBED_DIMENSIONS})"
                )
            all_vectors.append(values)

    if len(all_vectors) != len(texts):
        raise EmbedError("Embedding count mismatch")

    return all_vectors
