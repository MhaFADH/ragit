# Architecture

For schema, error handling, retries, and testing strategy see [design.md](design.md).

## Flow

```mermaid
flowchart LR
    Repos["GitHub / GitLab / Bitbucket<br/>(HTTPS, optional per-repo token)"]
    Var[("Airflow Variable<br/>docs_rag_repos")]

    Repos --> ProcessRepo
    Var --> GetRepos

    GetRepos[get_repos] --> ProcessRepo["process_repo<br/>(mapped per repo)"]
    ProcessRepo --> Aggregate[aggregate_changes]
    Aggregate --> Embed[embed_and_upsert]

    Documents[("documents")] --> ProcessRepo
    Embed --> Documents
    Embed --> Chunks[("chunks<br/>vector(1024)")]

    classDef store fill:#f6f8fa,stroke:#888;
    class Documents,Chunks,Var store;
```

## Stages

**1. Read config** — `get_repos` loads the `docs_rag_repos` Variable (a JSON list of repo configs).

**2. Diff per repo** — `process_repo` is mapped one task per entry; each instance shallow-clones the repo, walks every `.md`, sha256s it, and compares against the `documents` table (the embedded baseline). Output = added / modified / deleted change records.

**3. Flatten** — `aggregate_changes` merges per-repo lists into one stream and logs per-(repo, branch) counts.

**4. Embed + write** — `embed_and_upsert` splits each upserted file into header-aware token-bounded chunks, runs every chunk through BGE-large in one batched call, and replaces the file's row + chunks in one transaction. Deletes cascade via the FK from `chunks` to `documents`.

## Self-healing baseline

A `documents` row exists **only after** its chunks were committed in the same transaction. If stage 4 fails mid-batch, partial files are not marked. The next run sees them as still new / modified and reprocesses automatically.

## Runtime

| Container | Image | Role |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg18` | Hosts the Airflow metadata DB and the `docs_rag` app DB. Schema applied once via `/docker-entrypoint-initdb.d/`. |
| `airflow` | extends `apache/airflow:3.1.6-python3.12` | Runs `airflow standalone`. BGE-large ONNX + tokenizer baked into the image at build time. |

Compose pulls `${AIRFLOW_FERNET_KEY}`, `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`, `${POSTGRES_DB}` from `.env`. Admin login lives in `docker/admin_password.json`.
