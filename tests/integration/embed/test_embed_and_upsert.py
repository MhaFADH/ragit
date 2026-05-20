from __future__ import annotations

from typing import Any

import psycopg
import pytest
from _fakes import fake_embedder
from docs_rag.embed.embed_and_upsert import embed_and_upsert


@pytest.fixture(autouse=True)
def _stub_heavy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docs_rag.embed.utils.chunking.count_tokens", fake_embedder.count_tokens)
    monkeypatch.setattr("docs_rag.embed.utils.embedder.embed_batch", fake_embedder.embed_batch)


def _added(repo: str, path: str, content: str, sha: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "branch": "",
        "path": path,
        "status": "added",
        "content": content,
        "sha256": sha,
    }


def _deleted(repo: str, path: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "branch": "",
        "path": path,
        "status": "deleted",
        "content": None,
        "sha256": None,
    }


def _row_counts(conn: psycopg.Connection[Any]) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM documents")
        d_row = cur.fetchone()
        cur.execute("SELECT count(*) FROM chunks")
        c_row = cur.fetchone()
    assert d_row is not None and c_row is not None
    return int(d_row[0]), int(c_row[0])


def test_e2e_added_files_persisted_with_chunks(pg_conn: psycopg.Connection[Any]) -> None:
    changes = [
        _added("foo", "intro.md", "# Intro\n\nbody-a", "sha-a"),
        _added("foo", "guide.md", "# Guide\n\n## Auth\n\nbody-b", "sha-b"),
    ]
    embed_and_upsert.function(changes)

    docs, chunks = _row_counts(pg_conn)
    assert docs == 2
    assert chunks >= 2


def test_e2e_modified_file_replaces_chunks(pg_conn: psycopg.Connection[Any]) -> None:
    embed_and_upsert.function([_added("foo", "intro.md", "# Intro\n\noriginal", "sha-1")])
    docs_before, _ = _row_counts(pg_conn)

    modified = _added("foo", "intro.md", "# Intro\n\ncompletely new", "sha-2")
    modified["status"] = "modified"
    embed_and_upsert.function([modified])

    docs_after, _ = _row_counts(pg_conn)
    assert docs_after == docs_before
    with pg_conn.cursor() as cur:
        cur.execute("SELECT content FROM chunks")
        contents = [r[0] for r in cur.fetchall()]
    assert any("completely new" in c for c in contents)


def test_e2e_deletion_removes_document_and_cascades(
    pg_conn: psycopg.Connection[Any],
) -> None:
    embed_and_upsert.function([_added("foo", "gone.md", "# Gone\n\nbody", "sha-g")])
    assert _row_counts(pg_conn) != (0, 0)

    embed_and_upsert.function([_deleted("foo", "gone.md")])
    assert _row_counts(pg_conn) == (0, 0)


def test_e2e_empty_changes_no_db_writes(pg_conn: psycopg.Connection[Any]) -> None:
    embed_and_upsert.function([])
    assert _row_counts(pg_conn) == (0, 0)
