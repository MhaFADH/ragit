from __future__ import annotations

import os
from typing import Any

import psycopg


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(os.environ["DOCS_RAG_DATABASE_URL"])


def log_prefix(name: str, branch: str) -> str:
    return f"[{name}@{branch}]" if branch else f"[{name}]"
