from __future__ import annotations

from typing import Any

import numpy as np
import psycopg
from _fakes import fake_embedder
from docs_rag.embed.utils.store import (
    delete_document,
    register_pgvector,
    upsert_document_with_chunks,
)


def _row_counts(conn: psycopg.Connection[Any]) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        d_row = cur.fetchone()
        cur.execute("SELECT count(*) FROM chunks")
        c_row = cur.fetchone()
    assert d_row is not None and c_row is not None
    return int(d_row[0]), int(c_row[0])


def _chunks(
    *, count: int = 2, prefix: str = "x"
) -> list[tuple[int, str, str, int, np.ndarray[Any, Any]]]:
    return [
        (i, "Top > Mid", f"{prefix}-{i}", 10, fake_embedder._fake_vector(f"{prefix}-{i}"))
        for i in range(count)
    ]


def test_upsert_inserts_document_and_chunks(pg_conn: psycopg.Connection[Any]) -> None:
    register_pgvector(pg_conn)
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="",
        file_path="intro.md",
        sha256="h1",
        chunk_rows=_chunks(count=3),
    )
    docs, chunks = _row_counts(pg_conn)
    assert (docs, chunks) == (1, 3)


def test_upsert_replaces_old_chunks(pg_conn: psycopg.Connection[Any]) -> None:
    register_pgvector(pg_conn)
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="",
        file_path="intro.md",
        sha256="h1",
        chunk_rows=_chunks(count=5, prefix="old"),
    )
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="",
        file_path="intro.md",
        sha256="h2",
        chunk_rows=_chunks(count=2, prefix="new"),
    )
    docs, chunks = _row_counts(pg_conn)
    assert (docs, chunks) == (1, 2)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT content FROM chunks ORDER BY chunk_index")
        contents = [r[0] for r in cur.fetchall()]
    assert all(c.startswith("new-") for c in contents)


def test_upsert_empty_chunk_rows_keeps_document(pg_conn: psycopg.Connection[Any]) -> None:
    register_pgvector(pg_conn)
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="",
        file_path="empty.md",
        sha256="h-empty",
        chunk_rows=[],
    )
    docs, chunks = _row_counts(pg_conn)
    assert (docs, chunks) == (1, 0)


def test_delete_document_cascades_chunks(pg_conn: psycopg.Connection[Any]) -> None:
    register_pgvector(pg_conn)
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="",
        file_path="intro.md",
        sha256="h1",
        chunk_rows=_chunks(count=4),
    )
    delete_document(pg_conn, "foo", "", "intro.md")
    assert _row_counts(pg_conn) == (0, 0)


def test_upsert_isolates_by_repo_and_branch(pg_conn: psycopg.Connection[Any]) -> None:
    register_pgvector(pg_conn)
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="",
        file_path="a.md",
        sha256="h",
        chunk_rows=_chunks(count=2),
    )
    upsert_document_with_chunks(
        pg_conn,
        repo="foo",
        branch="develop",
        file_path="a.md",
        sha256="h",
        chunk_rows=_chunks(count=3),
    )
    upsert_document_with_chunks(
        pg_conn,
        repo="bar",
        branch="",
        file_path="a.md",
        sha256="h",
        chunk_rows=_chunks(count=1),
    )
    docs, chunks = _row_counts(pg_conn)
    assert (docs, chunks) == (3, 6)
