from __future__ import annotations

import logging
import tempfile
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

from airflow.sdk import task
from docs_rag.common import connect, log_prefix
from docs_rag.repo_diff.utils.git_ops import (
    redact_url,
    repo_name_from_url,
    shallow_clone,
)
from docs_rag.repo_diff.utils.hashing import compute_diff, walk_md_files
from docs_rag.repo_diff.utils.state import load_repo_state

log = logging.getLogger(__name__)

_LARGE_FILE_BYTES = 1_000_000


@task(retries=2, retry_delay=timedelta(minutes=2))
def process_repo(repo_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    url = repo_cfg["url"]
    branch = repo_cfg.get("branch") or ""
    name = repo_cfg.get("name") or repo_name_from_url(url)
    token = repo_cfg.get("token")
    prefix = log_prefix(name, branch)

    with tempfile.TemporaryDirectory(prefix="ragit_") as tmp:
        dest = Path(tmp) / name
        log.info(
            "%s cloning %s (branch=%s, auth=%s)",
            prefix,
            redact_url(url),
            branch or "<default>",
            "token" if token else "public",
        )
        shallow_clone(url, dest, branch, token=token)

        current = walk_md_files(dest)
        log.info("%s walked %d .md files", prefix, len(current))

        with closing(connect()) as conn:
            stored = load_repo_state(conn, name, branch)
        added, modified, deleted = compute_diff(current, stored)
        unchanged = len(current) - len(added) - len(modified)
        log.info(
            "%s diff: +%d added, ~%d modified, -%d deleted (%d unchanged)",
            prefix,
            len(added),
            len(modified),
            len(deleted),
            unchanged,
        )

        changes: list[dict[str, Any]] = []
        added_set = set(added)
        for path in added + modified:
            abs_path = dest / path
            try:
                content = abs_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                log.warning("%s skipping non-UTF-8 file: %s", prefix, path)
                continue
            if abs_path.stat().st_size > _LARGE_FILE_BYTES:
                log.warning("%s large file >1MB (proceeding): %s", prefix, path)
            changes.append(
                {
                    "repo": name,
                    "branch": branch,
                    "path": path,
                    "status": "added" if path in added_set else "modified",
                    "content": content,
                    "sha256": current[path],
                }
            )
        for path in deleted:
            changes.append(
                {
                    "repo": name,
                    "branch": branch,
                    "path": path,
                    "status": "deleted",
                    "content": None,
                    "sha256": None,
                }
            )

    return changes
