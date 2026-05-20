from __future__ import annotations

import logging
from contextlib import closing
from datetime import timedelta
from typing import Any

from airflow.sdk import task
from docs_rag.common import connect, log_prefix

log = logging.getLogger(__name__)


@task(retries=2, retry_delay=timedelta(minutes=1))
def embed_and_upsert(changes: list[dict[str, Any]]) -> None:
    from docs_rag.embed.utils import chunking, embedder, store

    if not changes:
        log.info("no changes")
        return

    deletes = [c for c in changes if c["status"] == "deleted"]
    upserts = [c for c in changes if c["status"] in ("added", "modified")]

    chunked: list[tuple[dict[str, Any], list[chunking.Chunk]]] = []
    all_texts: list[str] = []
    for c in upserts:
        chunks = chunking.split_markdown(c["content"])
        chunked.append((c, chunks))
        all_texts.extend(ch.content for ch in chunks)

    log.info(
        "%d upserts, %d deletes, %d chunks to embed",
        len(upserts),
        len(deletes),
        len(all_texts),
    )

    embeddings = embedder.embed_batch(all_texts) if all_texts else []

    with closing(connect()) as conn:
        store.register_pgvector(conn)

        for c in deletes:
            store.delete_document(conn, c["repo"], c["branch"], c["path"])
            log.info(
                "%s deleted %s",
                log_prefix(c["repo"], c["branch"]),
                c["path"],
            )

        offset = 0
        for c, chunks in chunked:
            chunk_rows: list[tuple[Any, ...]] = []
            for ch in chunks:
                chunk_rows.append(
                    (
                        ch.chunk_index,
                        ch.heading_path,
                        ch.content,
                        ch.token_count,
                        embeddings[offset],
                    )
                )
                offset += 1
            store.upsert_document_with_chunks(
                conn,
                repo=c["repo"],
                branch=c["branch"],
                file_path=c["path"],
                sha256=c["sha256"],
                chunk_rows=chunk_rows,
            )
            log.info(
                "%s upserted %s (%d chunks)",
                log_prefix(c["repo"], c["branch"]),
                c["path"],
                len(chunks),
            )
