from __future__ import annotations

import json
import math
from typing import Any


def parse_embedding(raw: Any) -> list[float]:
    if raw is None:
        raise ValueError("Missing embedding")
    if isinstance(raw, list):
        return [float(value) for value in raw]
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [float(value) for value in parsed]
    raise ValueError(f"Unsupported embedding format: {type(raw)!r}")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimension mismatch")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)
