from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from mcp_server.search import _mmr, _strip_internal, search


def _candidate(
    chunk_index: int,
    rerank_score: float,
    embedding: np.ndarray[Any, Any],
    content: str = "",
) -> dict[str, Any]:
    return {
        "chunk_index": chunk_index,
        "rerank_score": rerank_score,
        "cosine_score": rerank_score,
        "embedding": embedding,
        "content": content or f"chunk-{chunk_index}",
    }


def test_mmr_picks_highest_relevance_first() -> None:
    a = _candidate(0, rerank_score=0.9, embedding=np.array([1.0, 0.0, 0.0]))
    b = _candidate(1, rerank_score=0.5, embedding=np.array([0.0, 1.0, 0.0]))
    result = _mmr([a, b], top_k=1, lambda_=0.7)
    assert [chunk["chunk_index"] for chunk in result] == [0]


def test_mmr_balances_relevance_and_diversity() -> None:
    a = _candidate(0, rerank_score=0.9, embedding=np.array([1.0, 0.0]))
    near_duplicate = _candidate(1, rerank_score=0.89, embedding=np.array([1.0, 0.0]))
    diverse = _candidate(2, rerank_score=0.6, embedding=np.array([0.0, 1.0]))
    result = _mmr([a, near_duplicate, diverse], top_k=2, lambda_=0.5)
    indices = [chunk["chunk_index"] for chunk in result]
    assert indices[0] == 0
    assert indices[1] == 2


def test_mmr_stops_at_top_k() -> None:
    candidates = [
        _candidate(index, rerank_score=1.0 - index * 0.1, embedding=np.eye(5)[index])
        for index in range(5)
    ]
    result = _mmr(candidates, top_k=3, lambda_=0.7)
    assert len(result) == 3


def test_strip_internal_removes_embedding_field() -> None:
    candidate = _candidate(0, rerank_score=0.5, embedding=np.array([1.0]))
    stripped = _strip_internal([candidate])
    assert "embedding" not in stripped[0]


def test_search_returns_empty_when_pool_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.search.embed_query",
        lambda query: np.zeros(1024, dtype=np.float32),
    )
    monkeypatch.setattr(
        "mcp_server.search._cosine_pool",
        lambda *args, **kwargs: [],
    )
    assert search("anything", top_k=5) == []


def test_search_clamps_top_k_above_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_cosine_pool(
        query_embedding: Any, *, pool_size: int, repo: str | None, branch: str
    ) -> list[dict[str, Any]]:
        captured["pool_size"] = pool_size
        return []

    monkeypatch.setattr(
        "mcp_server.search.embed_query",
        lambda query: np.zeros(1024, dtype=np.float32),
    )
    monkeypatch.setattr("mcp_server.search._cosine_pool", fake_cosine_pool)
    search("query", top_k=9999)
    assert captured["pool_size"] == 50


def test_search_passes_branch_default_to_cosine_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_cosine_pool(
        query_embedding: Any, *, pool_size: int, repo: str | None, branch: str
    ) -> list[dict[str, Any]]:
        captured["branch"] = branch
        return []

    monkeypatch.setattr(
        "mcp_server.search.embed_query",
        lambda query: np.zeros(1024, dtype=np.float32),
    )
    monkeypatch.setattr("mcp_server.search._cosine_pool", fake_cosine_pool)
    search("anything", top_k=5)
    assert captured["branch"] == "main"


def test_search_passes_explicit_branch_to_cosine_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_cosine_pool(
        query_embedding: Any, *, pool_size: int, repo: str | None, branch: str
    ) -> list[dict[str, Any]]:
        captured["branch"] = branch
        return []

    monkeypatch.setattr(
        "mcp_server.search.embed_query",
        lambda query: np.zeros(1024, dtype=np.float32),
    )
    monkeypatch.setattr("mcp_server.search._cosine_pool", fake_cosine_pool)
    search("anything", top_k=5, branch="develop")
    assert captured["branch"] == "develop"
