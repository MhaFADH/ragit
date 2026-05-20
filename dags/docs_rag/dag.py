from __future__ import annotations

from datetime import datetime

from airflow.sdk import dag

from docs_rag.repo_diff.get_repos import get_repos
from docs_rag.repo_diff.process_repo import process_repo


@dag(
    dag_id="docs_rag_repo_diff",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["docs_rag"],
)
def docs_rag_repo_diff() -> None:
    process_repo.expand(repo_cfg=get_repos())


docs_rag_repo_diff()
