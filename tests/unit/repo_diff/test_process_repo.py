from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from docs_rag.repo_diff.process_repo import process_repo


def _wire_environment(
    monkeypatch: pytest.MonkeyPatch,
    src: Path,
    stored: dict[str, str],
) -> dict[str, Any]:
    clone_calls: dict[str, Any] = {}

    def fake_clone(
        url: str,
        dest: Path,
        branch: str = "",
        *,
        token: str | None = None,
    ) -> None:
        clone_calls["url"] = url
        clone_calls["branch"] = branch
        clone_calls["token"] = token
        shutil.copytree(src, dest)

    monkeypatch.setattr("docs_rag.repo_diff.process_repo.shallow_clone", fake_clone)
    monkeypatch.setattr("docs_rag.repo_diff.process_repo.connect", lambda: MagicMock())
    monkeypatch.setattr(
        "docs_rag.repo_diff.process_repo.load_repo_state",
        lambda conn, repo, branch: dict(stored),
    )
    return clone_calls


def _by_path(changes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {c["path"]: c for c in changes}


def test_first_run_marks_files_added(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "intro.md").write_text("# Hello")
    (src / "guide.md").write_text("# Guide")

    _wire_environment(monkeypatch, src, stored={})
    changes = process_repo.function({"url": "https://github.com/x/foo.git"})
    by_path = _by_path(changes)
    assert set(by_path) == {"intro.md", "guide.md"}
    assert all(c["status"] == "added" for c in changes)
    assert all(c["content"] is not None for c in changes)


def test_unchanged_files_omitted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import hashlib

    src = tmp_path / "repo"
    src.mkdir()
    (src / "intro.md").write_bytes(b"# Hello")
    sha = hashlib.sha256(b"# Hello").hexdigest()

    _wire_environment(monkeypatch, src, stored={"intro.md": sha})
    changes = process_repo.function({"url": "https://github.com/x/foo.git"})
    assert changes == []


def test_modified_file_replaces_baseline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "intro.md").write_text("new content")

    _wire_environment(monkeypatch, src, stored={"intro.md": "old-sha-hex"})
    changes = process_repo.function({"url": "https://github.com/x/foo.git"})
    assert len(changes) == 1
    assert changes[0]["status"] == "modified"
    assert changes[0]["content"] == "new content"


def test_deleted_file_emits_deletion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()

    _wire_environment(monkeypatch, src, stored={"old.md": "anything"})
    changes = process_repo.function({"url": "https://github.com/x/foo.git"})
    assert len(changes) == 1
    assert changes[0]["status"] == "deleted"
    assert changes[0]["content"] is None
    assert changes[0]["sha256"] is None


def test_public_repo_clones_without_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "a.md").write_text("x")

    calls = _wire_environment(monkeypatch, src, stored={})
    process_repo.function({"url": "https://github.com/public/foo.git"})
    assert calls["token"] is None


def test_private_repo_passes_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "a.md").write_text("x")

    calls = _wire_environment(monkeypatch, src, stored={})
    process_repo.function(
        {
            "url": "https://bitbucket.org/org/foo.git",
            "token": "bb_abc",
        }
    )
    assert calls["token"] == "bb_abc"


def test_repo_cfg_name_overrides_url_basename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "a.md").write_text("x")

    _wire_environment(monkeypatch, src, stored={})
    changes = process_repo.function({"url": "https://github.com/x/foo.git", "name": "custom"})
    assert all(c["repo"] == "custom" for c in changes)


def test_branch_propagated_into_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "a.md").write_text("x")

    _wire_environment(monkeypatch, src, stored={})
    changes = process_repo.function({"url": "https://github.com/x/foo.git", "branch": "develop"})
    assert all(c["branch"] == "develop" for c in changes)
