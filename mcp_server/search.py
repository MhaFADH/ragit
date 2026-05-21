from __future__ import annotations

import logging
from contextlib import closing
from typing import Any

import numpy as np
from pgvector.psycopg import register_vector

from mcp_server.db import connect
from mcp_server.embedder import embed_query, rerank

log = logging.getLogger(__name__)

_CANDIDATE_POOL = 20
_MMR_LAMBDA = 0.7
_MAX_TOP_K = 50
DEFAULT_BRANCH = "main"


def _cosine_pool(
    query_embedding: np.ndarray[Any, Any],
    *,
    pool_size: int,
    repo: str | None,
    branch: str,
) -> list[dict[str, Any]]:
    with closing(connect()) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            if repo:
                cursor.execute(
                    """
                    SELECT repo, branch, file_path, chunk_index, heading_path,
                           content, token_count, embedding,
                           1 - (embedding <=> %s) AS cosine_score
                    FROM chunks
                    WHERE repo = %s AND branch = %s
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (query_embedding, repo, branch, query_embedding, pool_size),
                )
            else:
                cursor.execute(
                    """
                    SELECT repo, branch, file_path, chunk_index, heading_path,
                           content, token_count, embedding,
                           1 - (embedding <=> %s) AS cosine_score
                    FROM chunks
                    WHERE branch = %s
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (query_embedding, branch, query_embedding, pool_size),
                )
            assert cursor.description is not None
            column_names = [column[0] for column in cursor.description]
            return [dict(zip(column_names, row, strict=True)) for row in cursor.fetchall()]


def _rerank_candidates(query: str, candidates: list[dict[str, Any]]) -> None:
    if not candidates:
        return
    contents = [candidate["content"] for candidate in candidates]
    try:
        scores = rerank(query, contents)
    except Exception:
        log.exception("rerank failed, falling back to cosine order")
        for candidate in candidates:
            candidate["rerank_score"] = candidate["cosine_score"]
        return
    for candidate, score in zip(candidates, scores, strict=True):
        candidate["rerank_score"] = float(score)
    candidates.sort(key=lambda candidate: candidate["rerank_score"], reverse=True)


def _cosine_similarity(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> float:
    norm_left = float(np.linalg.norm(left))
    norm_right = float(np.linalg.norm(right))
    if not norm_left or not norm_right:
        return 0.0
    return float(np.dot(left, right) / (norm_left * norm_right))


def _mmr(
    candidates: list[dict[str, Any]],
    top_k: int,
    lambda_: float,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    remaining = list(candidates)
    while remaining and len(selected) < top_k:
        best_index = 0
        best_score = -float("inf")
        for index, candidate in enumerate(remaining):
            relevance = candidate["rerank_score"]
            if not selected:
                score = relevance
            else:
                max_similarity = max(
                    _cosine_similarity(candidate["embedding"], picked["embedding"])
                    for picked in selected
                )
                score = lambda_ * relevance - (1 - lambda_) * max_similarity
            if score > best_score:
                best_score = score
                best_index = index
        selected.append(remaining.pop(best_index))
    return selected


def _strip_internal(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for result in results:
        result.pop("embedding", None)
    return results


def search(
    query: str,
    *,
    top_k: int = 5,
    repo: str | None = None,
    branch: str = DEFAULT_BRANCH,
) -> list[dict[str, Any]]:
    clamped_top_k = max(1, min(top_k, _MAX_TOP_K))
    if clamped_top_k != top_k:
        log.warning("top_k=%d clamped to %d", top_k, clamped_top_k)

    query_embedding = embed_query(query)
    candidates = _cosine_pool(
        query_embedding,
        pool_size=max(_CANDIDATE_POOL, clamped_top_k),
        repo=repo,
        branch=branch,
    )
    if not candidates:
        return []

    _rerank_candidates(query, candidates)
    diversified = _mmr(candidates, top_k=clamped_top_k, lambda_=_MMR_LAMBDA)
    return _strip_internal(diversified)
