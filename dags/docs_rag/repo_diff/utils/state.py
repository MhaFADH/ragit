from __future__ import annotations

from typing import Any

import psycopg


def load_repo_state(
    conn: psycopg.Connection[Any],
    repo: str,
    branch: str,
) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT file_path, sha256 FROM documents WHERE repo = %s AND branch = %s",
            (repo, branch),
        )
        return {row[0]: row[1] for row in cur.fetchall()}
