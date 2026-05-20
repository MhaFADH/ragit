from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _docs_rag_database_url_env(
    docs_rag_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCS_RAG_DATABASE_URL", docs_rag_database_url)
