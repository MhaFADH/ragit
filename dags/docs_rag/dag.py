from __future__ import annotations

from datetime import datetime

from airflow.sdk import dag

from docs_rag.embed.embed_and_upsert import embed_and_upsert
from docs_rag.repo_diff.aggregate_changes import aggregate_changes
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
    per_repo = process_repo.expand(repo_cfg=get_repos())
    flat = aggregate_changes(per_repo)  # type: ignore[arg-type]
    embed_and_upsert(flat)  # type: ignore[arg-type]


docs_rag_repo_diff()
