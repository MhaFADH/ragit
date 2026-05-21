from __future__ import annotations

from threading import Lock
from typing import Any

import numpy as np

EMBED_MODEL = "BAAI/bge-large-en-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"

_embedder: Any = None
_reranker: Any = None
_embedder_lock = Lock()
_reranker_lock = Lock()


def get_embedder() -> Any:
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                from fastembed import TextEmbedding

                _embedder = TextEmbedding(model_name=EMBED_MODEL)
    return _embedder


def get_reranker() -> Any:
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                _reranker = TextCrossEncoder(model_name=RERANK_MODEL)
    return _reranker


def embed_query(query: str) -> np.ndarray[Any, Any]:
    return next(iter(get_embedder().embed([query])))


def rerank(query: str, contents: list[str]) -> list[float]:
    return [float(score) for score in get_reranker().rerank(query, contents)]
