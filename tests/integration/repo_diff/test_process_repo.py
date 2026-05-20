from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import psycopg
import pytest
from docs_rag.repo_diff.process_repo import process_repo


def _patch_clone(monkeypatch: pytest.MonkeyPatch, src: Path) -> None:
    def fake_clone(
        url: str,
        dest: Path,
        branch: str = "",
        *,
        token: str | None = None,
    ) -> None:
        shutil.copytree(src, dest)

    monkeypatch.setattr("docs_rag.repo_diff.process_repo.shallow_clone", fake_clone)


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


def test_first_run_all_added_against_empty_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pg_conn: psycopg.Connection[Any],
) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "intro.md").write_text("# hello")
    _patch_clone(monkeypatch, src)

    changes = process_repo.function({"url": "https://github.com/x/foo.git"})
    assert len(changes) == 1
    assert changes[0]["status"] == "added"
    assert changes[0]["path"] == "intro.md"


def test_unchanged_file_omitted_against_real_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pg_conn: psycopg.Connection[Any],
) -> None:
    content = b"# stable"
    sha = hashlib.sha256(content).hexdigest()
    _insert_document(pg_conn, "foo", "", "intro.md", sha)

    src = tmp_path / "repo"
    src.mkdir()
    (src / "intro.md").write_bytes(content)
    _patch_clone(monkeypatch, src)

    changes = process_repo.function({"url": "https://github.com/x/foo.git", "name": "foo"})
    assert changes == []


def test_modified_file_detected_against_real_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pg_conn: psycopg.Connection[Any],
) -> None:
    _insert_document(pg_conn, "foo", "", "intro.md", "old-sha")

    src = tmp_path / "repo"
    src.mkdir()
    (src / "intro.md").write_text("new content")
    _patch_clone(monkeypatch, src)

    changes = process_repo.function({"url": "https://github.com/x/foo.git", "name": "foo"})
    assert len(changes) == 1
    assert changes[0]["status"] == "modified"
    assert changes[0]["content"] == "new content"


def test_deleted_file_detected_against_real_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pg_conn: psycopg.Connection[Any],
) -> None:
    _insert_document(pg_conn, "foo", "", "gone.md", "old-sha")

    src = tmp_path / "repo"
    src.mkdir()
    _patch_clone(monkeypatch, src)

    changes = process_repo.function({"url": "https://github.com/x/foo.git", "name": "foo"})
    assert len(changes) == 1
    assert changes[0]["status"] == "deleted"
    assert changes[0]["path"] == "gone.md"
