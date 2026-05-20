from __future__ import annotations

import os
from typing import Any

import psycopg


def connect() -> psycopg.Connection[Any]:
    url = os.environ.get("DOCS_RAG_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DOCS_RAG_DATABASE_URL not set. "
            "Example: postgresql://docs_rag:docs_rag@localhost:5432/docs_rag"
        )
    return psycopg.connect(url)
