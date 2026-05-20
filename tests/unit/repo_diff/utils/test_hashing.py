from __future__ import annotations

import hashlib
from pathlib import Path

from docs_rag.repo_diff.utils.hashing import compute_diff, walk_md_files


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_walk_md_files_empty_dir(tmp_path: Path) -> None:
    assert walk_md_files(tmp_path) == {}


def test_walk_md_files_picks_md_only(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"hello")
    (tmp_path / "b.txt").write_bytes(b"hello")
    result = walk_md_files(tmp_path)
    assert set(result.keys()) == {"a.md"}
    assert result["a.md"] == _sha256(b"hello")


def test_walk_md_files_nested_posix_paths(tmp_path: Path) -> None:
    nested = tmp_path / "docs" / "guide"
    nested.mkdir(parents=True)
    (nested / "intro.md").write_bytes(b"hi")
    result = walk_md_files(tmp_path)
    assert "docs/guide/intro.md" in result


def test_walk_md_files_skips_symlinked_dirs(tmp_path: Path) -> None:
    outside = tmp_path.parent / "ragit_walk_target"
    outside.mkdir(exist_ok=True)
    (outside / "linked.md").write_bytes(b"x")
    try:
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)
        result = walk_md_files(tmp_path)
        assert "link/linked.md" not in result
    finally:
        for child in outside.iterdir():
            child.unlink()
        outside.rmdir()


def test_compute_diff_both_empty() -> None:
    assert compute_diff({}, {}) == ([], [], [])


def test_compute_diff_all_added() -> None:
    added, modified, deleted = compute_diff({"a.md": "h1", "b.md": "h2"}, {})
    assert added == ["a.md", "b.md"]
    assert modified == []
    assert deleted == []


def test_compute_diff_all_deleted() -> None:
    added, modified, deleted = compute_diff({}, {"a.md": "h1"})
    assert added == []
    assert modified == []
    assert deleted == ["a.md"]


def test_compute_diff_modified() -> None:
    added, modified, deleted = compute_diff({"a.md": "new"}, {"a.md": "old"})
    assert added == []
    assert modified == ["a.md"]
    assert deleted == []


def test_compute_diff_unchanged_omitted() -> None:
    added, modified, deleted = compute_diff({"a.md": "h"}, {"a.md": "h"})
    assert added == []
    assert modified == []
    assert deleted == []


def test_compute_diff_mixed_results_are_sorted() -> None:
    current = {"z.md": "h", "a.md": "h1_new", "k.md": "kept"}
    stored = {"a.md": "h1_old", "k.md": "kept", "old.md": "gone"}
    added, modified, deleted = compute_diff(current, stored)
    assert added == ["z.md"]
    assert modified == ["a.md"]
    assert deleted == ["old.md"]
