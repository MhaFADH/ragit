from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from airflow.sdk import Variable, task

log = logging.getLogger(__name__)

_REPOS_VAR = "docs_rag_repos"


@task(retries=1, retry_delay=timedelta(seconds=30))
def get_repos() -> list[dict[str, Any]]:
    repos = Variable.get(_REPOS_VAR, default=None, deserialize_json=True)
    if repos is None:
        raise RuntimeError(
            f"Airflow Variable '{_REPOS_VAR}' not set. "
            "Create it via Admin -> Variables with a JSON list value, e.g. "
            '[{"url": "https://bitbucket.org/org/foo.git"}]'
        )
    if not isinstance(repos, list) or not repos:
        raise RuntimeError(
            f"Variable '{_REPOS_VAR}' must be a non-empty JSON list of dicts; "
            f"got {type(repos).__name__}"
        )
    log.info("loaded %d repo entries", len(repos))
    return repos
