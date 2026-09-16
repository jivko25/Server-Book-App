from app.services.rag_vector import cosine_similarity, parse_embedding


def test_parse_embedding_from_list() -> None:
    assert parse_embedding([1.0, 0.0, 0.0]) == [1.0, 0.0, 0.0]


def test_parse_embedding_from_json_string() -> None:
    assert parse_embedding("[0.5, 0.5, 0.0]") == [0.5, 0.5, 0.0]


def test_cosine_similarity_identical() -> None:
    vector = [1.0, 2.0, 3.0]
    assert cosine_similarity(vector, vector) == 1.0
