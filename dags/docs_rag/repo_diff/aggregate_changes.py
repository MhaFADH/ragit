from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from airflow.sdk import task
from docs_rag.common import log_prefix

log = logging.getLogger(__name__)


@task(retries=1, retry_delay=timedelta(seconds=30))
def aggregate_changes(per_repo: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    summaries: dict[tuple[str, str], dict[str, int]] = {}
    for changes in per_repo:
        for c in changes:
            flat.append(c)
            key = (c["repo"], c["branch"])
            summary = summaries.setdefault(key, {"added": 0, "modified": 0, "deleted": 0})
            summary[c["status"]] += 1
    for (repo, branch), s in summaries.items():
        log.info(
            "%s: +%d added, ~%d modified, -%d deleted",
            log_prefix(repo, branch),
            s["added"],
            s["modified"],
            s["deleted"],
        )
    log.info("total %d change records", len(flat))
    return flat
