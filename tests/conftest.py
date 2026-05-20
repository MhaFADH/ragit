from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from testcontainers.postgres import PostgresContainer

_INIT_SQL = Path(__file__).resolve().parents[1] / "config" / "docs_rag" / "init-docs-rag-db.sql"


@pytest.fixture(scope="session")
def docs_rag_database_url() -> Iterator[str]:
    container = PostgresContainer(
        "pgvector/pgvector:pg18",
        driver="psycopg",
    ).with_volume_mapping(
        str(_INIT_SQL),
        "/docker-entrypoint-initdb.d/10-docs-rag.sql",
        mode="ro",
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        yield f"postgresql://docs_rag:docs_rag@{host}:{port}/docs_rag"


@pytest.fixture
def pg_conn(docs_rag_database_url: str) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    with psycopg.connect(docs_rag_database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE chunks, documents CASCADE")
        conn.commit()
        yield conn
