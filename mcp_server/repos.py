from __future__ import annotations

from contextlib import closing
from typing import Any

from mcp_server.db import connect


def list_repos() -> list[dict[str, Any]]:
    with closing(connect()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT repo, branch, COUNT(DISTINCT file_path) AS file_count
            FROM documents
            GROUP BY repo, branch
            ORDER BY repo, branch
            """
        )
        assert cursor.description is not None
        column_names = [column[0] for column in cursor.description]
        return [dict(zip(column_names, row, strict=True)) for row in cursor.fetchall()]


def index_status() -> list[dict[str, Any]]:
    with closing(connect()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT d.repo, d.branch,
                   COUNT(DISTINCT d.file_path) AS file_count,
                   COUNT(c.id) AS chunk_count,
                   COALESCE(SUM(c.token_count), 0) AS total_tokens
            FROM documents d
            LEFT JOIN chunks c USING (repo, branch, file_path)
            GROUP BY d.repo, d.branch
            ORDER BY d.repo, d.branch
            """
        )
        assert cursor.description is not None
        column_names = [column[0] for column in cursor.description]
        return [dict(zip(column_names, row, strict=True)) for row in cursor.fetchall()]
