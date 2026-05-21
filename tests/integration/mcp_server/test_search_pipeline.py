from __future__ import annotations

from typing import Any

import psycopg
import pytest
from _fakes import fake_embedder, fake_reranker
from docs_rag.embed.utils.store import register_pgvector


@pytest.fixture(autouse=True)
def _stub_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.embedder.embed_query",
        lambda query: fake_embedder._fake_vector(query),
    )
    monkeypatch.setattr("mcp_server.embedder.rerank", fake_reranker.rerank)
    monkeypatch.setattr(
        "mcp_server.search.embed_query",
        lambda query: fake_embedder._fake_vector(query),
    )
    monkeypatch.setattr("mcp_server.search.rerank", fake_reranker.rerank)


def _seed(
    pg_conn: psycopg.Connection[Any],
    repo: str,
    branch: str,
    file_path: str,
    chunks: list[tuple[int, str, str]],
) -> None:
    register_pgvector(pg_conn)
    with pg_conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO documents (repo, branch, file_path, sha256) VALUES (%s, %s, %s, %s)",
            (repo, branch, file_path, "sha-" + file_path),
        )
        for chunk_index, heading_path, content in chunks:
            cursor.execute(
                """
                INSERT INTO chunks
                    (repo, branch, file_path, chunk_index, heading_path,
                     content, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    repo,
                    branch,
                    file_path,
                    chunk_index,
                    heading_path,
                    content,
                    max(1, len(content) // 4),
                    fake_embedder._fake_vector(content),
                ),
            )
    pg_conn.commit()


def test_search_empty_chunks_returns_empty(pg_conn: psycopg.Connection[Any]) -> None:
    from mcp_server.search import search

    assert search("anything", top_k=5) == []


def test_search_returns_results_with_expected_fields(
    pg_conn: psycopg.Connection[Any],
) -> None:
    _seed(
        pg_conn,
        "alpha",
        "main",
        "intro.md",
        [(0, "Intro", "How to authenticate"), (1, "Intro", "Configure timeouts")],
    )
    from mcp_server.search import search

    results = search("auth", top_k=2)
    assert len(results) <= 2
    first = results[0]
    assert "embedding" not in first
    assert {
        "repo",
        "branch",
        "file_path",
        "chunk_index",
        "content",
        "cosine_score",
        "rerank_score",
    }.issubset(first.keys())


def test_search_respects_repo_filter(pg_conn: psycopg.Connection[Any]) -> None:
    _seed(pg_conn, "alpha", "main", "intro.md", [(0, "Intro", "alpha content")])
    _seed(pg_conn, "beta", "main", "intro.md", [(0, "Intro", "beta content")])
    from mcp_server.search import search

    alpha_only = search("anything", top_k=5, repo="alpha")
    assert {result["repo"] for result in alpha_only} == {"alpha"}


def test_search_falls_back_when_reranker_raises(
    monkeypatch: pytest.MonkeyPatch, pg_conn: psycopg.Connection[Any]
) -> None:
    _seed(
        pg_conn,
        "alpha",
        "main",
        "intro.md",
        [(0, "Intro", "one"), (1, "Intro", "two")],
    )

    def broken_rerank(query: str, contents: list[str]) -> list[float]:
        raise RuntimeError("reranker exploded")

    monkeypatch.setattr("mcp_server.search.rerank", broken_rerank)
    from mcp_server.search import search

    results = search("anything", top_k=2)
    assert len(results) <= 2
    assert all("rerank_score" in result for result in results)


def test_search_clamps_top_k_to_max(
    monkeypatch: pytest.MonkeyPatch, pg_conn: psycopg.Connection[Any]
) -> None:
    chunks = [(index, "Section", f"chunk {index}") for index in range(60)]
    _seed(pg_conn, "alpha", "main", "huge.md", chunks)
    from mcp_server.search import search

    results = search("anything", top_k=100)
    assert len(results) <= 50


def test_search_filters_by_branch(pg_conn: psycopg.Connection[Any]) -> None:
    _seed(pg_conn, "alpha", "main", "intro.md", [(0, "Intro", "main content")])
    _seed(pg_conn, "alpha", "develop", "intro.md", [(0, "Intro", "develop content")])
    from mcp_server.search import search

    main_only = search("anything", top_k=5)
    assert {result["branch"] for result in main_only} == {"main"}

    develop_only = search("anything", top_k=5, branch="develop")
    assert {result["branch"] for result in develop_only} == {"develop"}
