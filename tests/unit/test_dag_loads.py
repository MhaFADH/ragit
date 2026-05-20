from __future__ import annotations

from airflow.dag_processing.dagbag import DagBag


def test_dagbag_loads_without_errors() -> None:
    bag = DagBag("dags", include_examples=False)
    assert not bag.import_errors, bag.import_errors


def test_docs_rag_dag_registered() -> None:
    bag = DagBag("dags", include_examples=False)
    assert "docs_rag_repo_diff" in bag.dags
