from __future__ import annotations

from typing import Any

from docs_rag.repo_diff.aggregate_changes import aggregate_changes


def _added(repo: str, branch: str, path: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "branch": branch,
        "path": path,
        "status": "added",
        "content": "x",
        "sha256": "h",
    }


def _deleted(repo: str, branch: str, path: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "branch": branch,
        "path": path,
        "status": "deleted",
        "content": None,
        "sha256": None,
    }


def test_aggregate_empty() -> None:
    assert aggregate_changes.function([]) == []


def test_aggregate_empty_inner_lists() -> None:
    assert aggregate_changes.function([[], []]) == []


def test_aggregate_flattens_preserving_order() -> None:
    a = _added("foo", "", "a.md")
    b = _added("foo", "", "b.md")
    c = _deleted("bar", "develop", "old.md")
    result = aggregate_changes.function([[a, b], [c]])
    assert result == [a, b, c]


def test_aggregate_isolates_repo_branch_pairs() -> None:
    foo_main = _added("foo", "", "x.md")
    foo_dev = _added("foo", "develop", "x.md")
    bar = _added("bar", "", "x.md")
    result = aggregate_changes.function([[foo_main], [foo_dev], [bar]])
    assert len(result) == 3
