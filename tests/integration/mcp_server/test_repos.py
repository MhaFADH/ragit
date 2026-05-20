from __future__ import annotations

from typing import Any

import psycopg

from mcp_server.repos import index_status, list_repos


def _seed_documents(conn: psycopg.Connection[Any]) -> None:
    rows = [
        ("alpha", "", "intro.md", "h1"),
        ("alpha", "", "guide.md", "h2"),
        ("alpha", "develop", "intro.md", "h3"),
        ("beta", "", "readme.md", "h4"),
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO documents (repo, branch, file_path, sha256) VALUES (%s, %s, %s, %s)",
            rows,
        )
    conn.commit()


def _seed_chunks(
    conn: psycopg.Connection[Any],
    repo: str,
    branch: str,
    file_path: str,
    chunks: int,
    token_count: int,
) -> None:
    import numpy as np
    from docs_rag.embed.utils.store import register_pgvector

    register_pgvector(conn)
    with conn.cursor() as cur:
        for i in range(chunks):
            cur.execute(
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
                    i,
                    "",
                    f"chunk {i}",
                    token_count,
                    np.zeros(1024, dtype=np.float32),
                ),
            )
    conn.commit()


def test_list_repos_empty_when_no_docs(pg_conn: psycopg.Connection[Any]) -> None:
    assert list_repos() == []


def test_list_repos_groups_by_repo_and_branch(pg_conn: psycopg.Connection[Any]) -> None:
    _seed_documents(pg_conn)
    result = list_repos()
    by_key = {(r["repo"], r["branch"]): r["file_count"] for r in result}
    assert by_key == {
        ("alpha", ""): 2,
        ("alpha", "develop"): 1,
        ("beta", ""): 1,
    }


def test_index_status_returns_zero_chunks_when_documents_empty(
    pg_conn: psycopg.Connection[Any],
) -> None:
    _seed_documents(pg_conn)
    result = index_status()
    by_key = {(r["repo"], r["branch"]): r for r in result}
    assert by_key[("alpha", "")]["file_count"] == 2
    assert by_key[("alpha", "")]["chunk_count"] == 0
    assert by_key[("alpha", "")]["total_tokens"] == 0


def test_index_status_aggregates_chunks_and_tokens(pg_conn: psycopg.Connection[Any]) -> None:
    _seed_documents(pg_conn)
    _seed_chunks(pg_conn, "alpha", "", "intro.md", chunks=3, token_count=10)
    _seed_chunks(pg_conn, "alpha", "", "guide.md", chunks=2, token_count=20)

    result = index_status()
    alpha_main = next(r for r in result if r["repo"] == "alpha" and r["branch"] == "")
    assert alpha_main["chunk_count"] == 5
    assert alpha_main["total_tokens"] == 3 * 10 + 2 * 20
