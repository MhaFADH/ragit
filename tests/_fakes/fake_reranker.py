from __future__ import annotations

import hashlib


def rerank(query: str, contents: list[str]) -> list[float]:
    return [_score(query, content) for content in contents]


def _score(query: str, content: str) -> float:
    digest = hashlib.sha256(f"{query}::{content}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / float(1 << 32)
