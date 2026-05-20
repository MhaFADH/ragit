from __future__ import annotations

from typing import Any

import psycopg
from docs_rag.repo_diff.utils.state import load_repo_state


def _insert_document(
    conn: psycopg.Connection[Any],
    repo: str,
    branch: str,
    file_path: str,
    sha256: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (repo, branch, file_path, sha256) VALUES (%s, %s, %s, %s)",
            (repo, branch, file_path, sha256),
        )
    conn.commit()


def test_load_repo_state_empty_for_unseen_repo(pg_conn: psycopg.Connection[Any]) -> None:
    assert load_repo_state(pg_conn, "foo", "") == {}


def test_load_repo_state_returns_paths_and_hashes(
    pg_conn: psycopg.Connection[Any],
) -> None:
    _insert_document(pg_conn, "foo", "", "intro.md", "h1")
    _insert_document(pg_conn, "foo", "", "guide.md", "h2")
    result = load_repo_state(pg_conn, "foo", "")
    assert result == {"intro.md": "h1", "guide.md": "h2"}


def test_load_repo_state_isolates_by_repo(pg_conn: psycopg.Connection[Any]) -> None:
    _insert_document(pg_conn, "foo", "", "a.md", "h1")
    _insert_document(pg_conn, "bar", "", "a.md", "h2")
    assert load_repo_state(pg_conn, "foo", "") == {"a.md": "h1"}
    assert load_repo_state(pg_conn, "bar", "") == {"a.md": "h2"}


def test_load_repo_state_isolates_by_branch(pg_conn: psycopg.Connection[Any]) -> None:
    _insert_document(pg_conn, "foo", "", "a.md", "main_hash")
    _insert_document(pg_conn, "foo", "develop", "a.md", "dev_hash")
    assert load_repo_state(pg_conn, "foo", "") == {"a.md": "main_hash"}
    assert load_repo_state(pg_conn, "foo", "develop") == {"a.md": "dev_hash"}
