from unittest.mock import MagicMock, patch

from app.services.gemini import GeminiUpstreamError
from app.services.rag_embeddings import EMBED_DIMENSIONS, embed_passages


def _mock_embedding(values: list[float]) -> MagicMock:
    embedding = MagicMock()
    embedding.values = values
    return embedding


def test_embed_passages_returns_768_dim_vectors() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.embeddings = [
        _mock_embedding([0.0] * EMBED_DIMENSIONS),
        _mock_embedding([1.0] * EMBED_DIMENSIONS),
    ]
    mock_client.models.embed_content.return_value = mock_response

    with patch("app.services.rag_embeddings._build_client", return_value=mock_client):
        vectors = embed_passages(["Alpha passage", "Beta passage"])

    assert len(vectors) == 2
    assert len(vectors[0]) == EMBED_DIMENSIONS
    mock_client.models.embed_content.assert_called_once()


def test_embed_passages_wraps_model_errors() -> None:
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = RuntimeError("upstream failed")

    with patch("app.services.rag_embeddings._build_client", return_value=mock_client):
        try:
            embed_passages(["Broken passage"])
        except GeminiUpstreamError as exc:
            assert "upstream failed" in str(exc)
        else:
            raise AssertionError("Expected GeminiUpstreamError")
