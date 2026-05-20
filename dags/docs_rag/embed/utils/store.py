from __future__ import annotations

from typing import Any

import psycopg


def register_pgvector(conn: psycopg.Connection[Any]) -> None:
    from pgvector.psycopg import register_vector

    register_vector(conn)


def delete_document(
    conn: psycopg.Connection[Any],
    repo: str,
    branch: str,
    file_path: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM documents WHERE repo = %s AND branch = %s AND file_path = %s",
            (repo, branch, file_path),
        )
    conn.commit()


def upsert_document_with_chunks(
    conn: psycopg.Connection[Any],
    *,
    repo: str,
    branch: str,
    file_path: str,
    sha256: str,
    chunk_rows: list[tuple[Any, ...]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM documents WHERE repo = %s AND branch = %s AND file_path = %s",
            (repo, branch, file_path),
        )
        cur.execute(
            "INSERT INTO documents (repo, branch, file_path, sha256) VALUES (%s, %s, %s, %s)",
            (repo, branch, file_path, sha256),
        )
        if chunk_rows:
            cur.executemany(
                """
                INSERT INTO chunks
                    (repo, branch, file_path, chunk_index, heading_path,
                     content, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (repo, branch, file_path, idx, hp, content, tc, emb)
                    for (idx, hp, content, tc, emb) in chunk_rows
                ],
            )
    conn.commit()
