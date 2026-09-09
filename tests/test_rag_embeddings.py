from unittest.mock import MagicMock, patch

import numpy as np

from app.services.rag_embeddings import EMBED_DIMENSIONS, EmbedError, embed_passages


def test_embed_passages_returns_768_dim_vectors() -> None:
    mock_model = MagicMock()
    mock_model.embed.return_value = [
        np.zeros(EMBED_DIMENSIONS, dtype=np.float32),
        np.ones(EMBED_DIMENSIONS, dtype=np.float32),
    ]

    with patch("app.services.rag_embeddings._get_model", return_value=mock_model):
        vectors = embed_passages(["Alpha passage", "Beta passage"])

    assert len(vectors) == 2
    assert len(vectors[0]) == EMBED_DIMENSIONS
    mock_model.embed.assert_called_once()


def test_embed_passages_wraps_model_errors() -> None:
    mock_model = MagicMock()
    mock_model.embed.side_effect = RuntimeError("onnx failed")

    with patch("app.services.rag_embeddings._get_model", return_value=mock_model):
        try:
            embed_passages(["Broken passage"])
        except EmbedError as exc:
            assert "onnx failed" in str(exc)
        else:
            raise AssertionError("Expected EmbedError")
