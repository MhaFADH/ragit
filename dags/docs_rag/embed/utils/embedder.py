from __future__ import annotations

from threading import Lock
from typing import Any

import numpy as np

MODEL_NAME = "BAAI/bge-large-en-v1.5"
EMBED_DIM = 1024
BATCH_SIZE = 32
MAX_TOKENS = 512

_model: Any = None
_tokenizer: Any = None
_model_lock = Lock()
_tokenizer_lock = Lock()


def get_model() -> Any:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from fastembed import TextEmbedding

                _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def get_tokenizer() -> Any:
    global _tokenizer
    if _tokenizer is None:
        with _tokenizer_lock:
            if _tokenizer is None:
                from tokenizers import Tokenizer

                _tokenizer = Tokenizer.from_pretrained(MODEL_NAME)
    return _tokenizer


def count_tokens(text: str) -> int:
    return len(get_tokenizer().encode(text).ids)


def embed_batch(texts: list[str]) -> list[np.ndarray[Any, Any]]:
    if not texts:
        return []
    return list(get_model().embed(texts, batch_size=BATCH_SIZE))
