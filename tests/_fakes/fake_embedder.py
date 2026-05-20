from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

EMBED_DIM = 1024


def embed_batch(texts: list[str]) -> list[np.ndarray[Any, Any]]:
    return [_fake_vector(t) for t in texts]


def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fake_vector(text: str) -> np.ndarray[Any, Any]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")
    rng = np.random.default_rng(seed)
    v: np.ndarray[Any, Any] = rng.standard_normal(EMBED_DIM, dtype=np.float32)
    norm = float(np.linalg.norm(v))
    return v / norm if norm else v
