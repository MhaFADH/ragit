from __future__ import annotations

import pytest

from mcp_server.db import connect


def test_connect_raises_when_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCS_RAG_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DOCS_RAG_DATABASE_URL"):
        connect()


def test_connect_raises_when_url_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCS_RAG_DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="DOCS_RAG_DATABASE_URL"):
        connect()
