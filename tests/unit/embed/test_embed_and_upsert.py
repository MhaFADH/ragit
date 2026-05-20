from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from _fakes import fake_embedder
from docs_rag.embed.embed_and_upsert import embed_and_upsert


@pytest.fixture(autouse=True)
def _wire_module_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docs_rag.embed.utils.chunking.count_tokens", fake_embedder.count_tokens)
    monkeypatch.setattr("docs_rag.embed.utils.embedder.embed_batch", fake_embedder.embed_batch)
    monkeypatch.setattr("docs_rag.embed.embed_and_upsert.connect", lambda: MagicMock())
    monkeypatch.setattr("docs_rag.embed.utils.store.register_pgvector", lambda conn: None)


def _added(path: str, content: str) -> dict[str, Any]:
    return {
        "repo": "foo",
        "branch": "",
        "path": path,
        "status": "added",
        "content": content,
        "sha256": "h-" + path,
    }


def _deleted(path: str) -> dict[str, Any]:
    return {
        "repo": "foo",
        "branch": "",
        "path": path,
        "status": "deleted",
        "content": None,
        "sha256": None,
    }


def test_no_changes_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        "docs_rag.embed.utils.store.upsert_document_with_chunks",
        lambda *args, **kwargs: called.append("upsert"),
    )
    monkeypatch.setattr(
        "docs_rag.embed.utils.store.delete_document",
        lambda *args, **kwargs: called.append("delete"),
    )
    embed_and_upsert.function([])
    assert called == []


def test_upsert_invokes_store_per_file(monkeypatch: pytest.MonkeyPatch) -> None:
    upserts: list[dict[str, Any]] = []

    def fake_upsert(
        conn: Any,
        *,
        repo: str,
        branch: str,
        file_path: str,
        sha256: str,
        chunk_rows: list[tuple[Any, ...]],
    ) -> None:
        upserts.append(
            {
                "repo": repo,
                "branch": branch,
                "file_path": file_path,
                "sha256": sha256,
                "chunk_count": len(chunk_rows),
            }
        )

    monkeypatch.setattr("docs_rag.embed.utils.store.upsert_document_with_chunks", fake_upsert)
    monkeypatch.setattr(
        "docs_rag.embed.utils.store.delete_document",
        lambda *a, **kw: None,
    )

    embed_and_upsert.function(
        [
            _added("a.md", "# A\n\nbody"),
            _added("b.md", "# B\n\nbody"),
        ]
    )
    assert len(upserts) == 2
    assert {u["file_path"] for u in upserts} == {"a.md", "b.md"}
    assert all(u["chunk_count"] >= 1 for u in upserts)


def test_deletes_invoke_delete_document(monkeypatch: pytest.MonkeyPatch) -> None:
    deletes: list[str] = []
    monkeypatch.setattr(
        "docs_rag.embed.utils.store.upsert_document_with_chunks",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "docs_rag.embed.utils.store.delete_document",
        lambda conn, repo, branch, file_path: deletes.append(file_path),
    )

    embed_and_upsert.function([_deleted("gone.md"), _deleted("other.md")])
    assert set(deletes) == {"gone.md", "other.md"}
