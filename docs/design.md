# ragit — Design

ragit is a documentation-RAG ingestion pipeline. It crawls a configured set of git repositories, detects added/modified/deleted markdown files between runs, chunks them, embeds the chunks with a local model, and writes them to a vector store. This document covers the ingestion path; consumers of the index (query API, MCP server) are described in their own designs.

---

## 1. Goals

1. Incremental, idempotent markdown ingestion across multiple git repositories.
2. Self-healing baseline: a file counts as "indexed" only once its chunks are committed, so any partial failure is retried automatically on the next run.
3. Production-grade hygiene: unit + integration tests, GitHub Actions CI gating every commit, architecture and runbook docs.
4. Comment-light code — narrative explanation lives in `docs/`, not inline.
5. Architecture leaves room for follow-on work (MCP server, query API, additional embedding backends) without committing to it now.

## 2. Stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Mature ML/embedding ecosystem; latest version supported by Airflow 3. |
| Orchestrator | Apache Airflow 3.x (LocalExecutor) | Mapped tasks parallelize cloning; built-in retry/XCom; familiar UI. DAG code imports from `airflow.sdk` (Task SDK introduced in 3.0). |
| Postgres driver | `psycopg` v3 | Modern adapter (replaces psycopg): server-side parameter binding by default, native async support if needed later. |
| Vector store | Postgres + `pgvector` (image `pgvector/pgvector:pg18`) | Single store for documents, chunks, and vectors; HNSW index on cosine. |
| Embedding model | `BAAI/bge-large-en-v1.5` via `fastembed` (ONNX, 1024d, 512-token input cap) | Strong English retrieval; ONNX runs CPU-only; weights baked into image for hermetic startup. |
| Chunking | `langchain-text-splitters` — header split + token-bounded recursive | Heading hierarchy preserved as chunk metadata and prepended to chunk text for vector context. |
| Code structure | Module layout under `dags/docs_rag/`, one responsibility per file | Each module testable in isolation; thin `@task` wrappers compose them. |
| Package manager | uv | Fast, deterministic, lockfile-backed. |
| Lint / format | ruff | Replaces black + isort + flake8. |
| Type checker | mypy | Standard. |
| Test runner | pytest | Standard. |
| Integration test infra | `testcontainers-python` | Real pg+pgvector container per CI job. |
| CI | GitHub Actions | Free, native Docker, runs on every push and PR. |

## 3. Repository layout

```
ragit/
├── dags/
│   └── docs_rag/
│       ├── __init__.py
│       ├── dag.py                          # DAG wiring only
│       ├── common.py                       # connect(), log_prefix()
│       ├── repo_diff/
│       │   ├── __init__.py
│       │   ├── get_repos.py                # @task
│       │   ├── process_repo.py             # @task (mapped per repo)
│       │   ├── aggregate_changes.py        # @task
│       │   └── utils/
│       │       ├── __init__.py
│       │       ├── git_ops.py              # pure: clone, URL/token injection
│       │       ├── hashing.py              # pure: walk_md_files, compute_diff
│       │       └── state.py                # load_repo_state(conn, ...)
│       └── embed/
│           ├── __init__.py
│           ├── embed_and_upsert.py         # @task
│           └── utils/
│               ├── __init__.py
│               ├── chunking.py             # pure: split_markdown
│               ├── embedder.py             # singleton model holder
│               └── store.py                # pg ops (delete, upsert tx)
├── config/
│   └── docs_rag/
│       ├── init-docs-rag-db.sql            # schema (single source of truth)
│       └── webserver_config.py             # Airflow webserver auth config
├── docker/
│   ├── Dockerfile.rag                      # Airflow image + deps + warm ONNX cache
│   └── docker-compose.yml                  # pg + airflow services
├── tests/
│   ├── conftest.py
│   ├── _fakes/
│   │   ├── fake_embedder.py
│   │   └── fixture_repo.py
│   ├── unit/
│   │   ├── repo_diff/
│   │   │   ├── utils/
│   │   │   │   ├── test_git_ops.py
│   │   │   │   └── test_hashing.py
│   │   │   └── test_aggregate_changes.py
│   │   └── embed/
│   │       └── utils/
│   │           ├── test_chunking.py
│   │           └── test_store.py
│   └── integration/
│       ├── test_state.py
│       ├── test_store_pg.py
│       ├── test_process_repo.py
│       └── test_embed_and_upsert.py
├── docs/
│   ├── design.md                           # this file
│   ├── architecture.md
│   └── runbook.md
├── .github/workflows/ci.yml
├── pyproject.toml
├── uv.lock
├── ruff.toml
├── mypy.ini
├── .gitignore
└── README.md
```

## 4. Components

### 4.1 Repo-diff stage (`dags/docs_rag/repo_diff/`)

| File | Symbol | Responsibility |
|---|---|---|
| `get_repos.py` | `@task get_repos() -> list[dict]` | Read Airflow Variable `docs_rag_repos`. Validate non-empty list. |
| `process_repo.py` | `@task process_repo(repo_cfg: dict) -> list[dict]` | Shallow clone, walk `.md`, diff against the embedded baseline, return change list. Mapped: one task instance per configured repo, parallel. |
| `aggregate_changes.py` | `@task aggregate_changes(per_repo: list[list[dict]]) -> list[dict]` | Flatten the mapped output and log per-repo counts. |
| `utils/git_ops.py` | `repo_name_from_url`, `_inject_token`, `shallow_clone` | Pure helpers + subprocess wrapper. Token injected only at clone-time; never logged. |
| `utils/hashing.py` | `walk_md_files`, `compute_diff` | Pure functions. POSIX-normalized path keys. |
| `utils/state.py` | `load_repo_state(conn, repo, branch) -> dict[str, str]` | Reads the `documents` table; returns `{file_path: sha256}`. |

### 4.2 Embed stage (`dags/docs_rag/embed/`)

| File | Symbol | Responsibility |
|---|---|---|
| `embed_and_upsert.py` | `@task embed_and_upsert(changes: list[dict]) -> None` | Chunk → batch embed in a single call → upsert/delete per file in its own transaction. Heavy deps lazy-imported. |
| `utils/chunking.py` | `split_markdown(content) -> list[Chunk]` | Two-stage: markdown header split, then token-bounded recursive split. Heading prefix prepended to chunk text so heading context propagates into the vector. |
| `utils/embedder.py` | `get_model`, `count_tokens`, `embed_batch(texts)` | Module-level singleton, guarded by a threading lock. Model loads once per worker process and is reused across task invocations. |
| `utils/store.py` | `register_pgvector`, `delete_document`, `upsert_document_with_chunks` | psycopg ops. DELETE+INSERT in one transaction per file; chunks vanish via the FK cascade. |

### 4.3 Shared

| File | Symbol | Responsibility |
|---|---|---|
| `common.py` | `connect()`, `log_prefix(name, branch)` | `connect()` reads `DOCS_RAG_DATABASE_URL`. Callers wrap in `closing(...)`. |
| `dag.py` | `@dag docs_rag_repo_diff()` | DAG wiring only. `schedule=None`, `max_active_runs=1`. |

### 4.4 Test-only

| File | Responsibility |
|---|---|
| `tests/_fakes/fake_embedder.py` | Deterministic stub: `embed_batch(texts) -> list[np.ndarray]`, vector derived from `sha256(text)`. Skips the 1.3 GB ONNX load in CI. |
| `tests/_fakes/fixture_repo.py` | Builds a tiny on-disk git repo with seed markdown files. Mutates (add/edit/rm) and commits between assertions. |

## 5. Data flow

### Stage 1 — repo_diff

```
get_repos
  └─ reads Variable docs_rag_repos
        → list[{url, branch?, name?}]
process_repo.expand(repo_cfg=repos)        # parallel mapped tasks
  ├─ reads Variable docs_rag_bitbucket_token
  ├─ shallow_clone(url, tmpdir, branch, token)
  ├─ current = walk_md_files(tmpdir)       # {posix_path: sha256}
  ├─ stored  = load_repo_state(conn, repo, branch)
  ├─ added, modified, deleted = compute_diff(current, stored)
  └─ returns list[{repo, branch, path, status, content?, sha256?}]
aggregate_changes(per_repo)
  └─ flatten list[list] → list[dict]
```

### Stage 2 — embed_and_upsert(changes)

```
upserts, deletes = partition(changes)
chunks_per_doc = {c: split_markdown(c.content) for c in upserts}
all_texts = flatten chunks
embeddings = embedder.embed_batch(all_texts)   # one batched call

with connect() as conn:
    register_pgvector(conn)
    for c in deletes:
        delete_document(conn, c.repo, c.branch, c.path)
    offset = 0
    for c, chunks in chunks_per_doc.items():
        rows = build_rows(chunks, embeddings[offset:offset + len(chunks)])
        upsert_document_with_chunks(conn, ..., rows)   # DELETE+INSERT in 1 tx
        offset += len(chunks)
```

### File state machine across runs

| Walk sees | `documents` row | Action |
|---|---|---|
| Yes, new path | absent | added → embed + insert |
| Yes, sha matches | present, same sha | omitted from changes |
| Yes, sha differs | present, different sha | modified → delete (FK cascade) + re-insert |
| No | present | deleted → delete (cascade kills chunks) |
| Yes, sha differs | absent | impossible — would be `added` |

**Self-healing invariant:** a row in `documents` exists iff its chunks were committed. A stage-2 failure leaves stage 1 seeing the file as still-to-process on the next run.

## 6. Schema

Authoritative SQL lives in `config/docs_rag/init-docs-rag-db.sql`. Applied once at Postgres container first boot. Abbreviated shape:

```sql
CREATE TABLE documents (
    repo      TEXT NOT NULL,
    branch    TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL,
    sha256    TEXT NOT NULL,
    PRIMARY KEY (repo, branch, file_path)
);

CREATE TABLE chunks (
    id           BIGSERIAL PRIMARY KEY,
    repo         TEXT NOT NULL,
    branch       TEXT NOT NULL DEFAULT '',
    file_path    TEXT NOT NULL,
    chunk_index  INT NOT NULL,
    heading_path TEXT,
    content      TEXT NOT NULL,
    token_count  INT NOT NULL,
    embedding    vector(1024) NOT NULL,
    FOREIGN KEY (repo, branch, file_path)
        REFERENCES documents (repo, branch, file_path)
        ON DELETE CASCADE
);

CREATE INDEX chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
```

`branch = ''` is the canonical representation of "remote default HEAD". No NULL.
Vector dimension (1024) is locked to the embedding model; changing models means dropping and rebuilding the `chunks` table.

## 7. Configuration

| Key | Where | Purpose |
|---|---|---|
| `docs_rag_repos` | Airflow Variable (JSON list) | List of `{url, branch?, name?}`. |
| `docs_rag_bitbucket_token` | Airflow Variable | Bitbucket repository access token, injected into clone URLs. |
| `DOCS_RAG_DATABASE_URL` | env (docker-compose) | psycopg connection string for the app DB. |

## 8. Error handling & retries

| Failure | Response |
|---|---|
| Missing/invalid `docs_rag_repos` Variable | `RuntimeError` with remediation hint. |
| Missing `docs_rag_bitbucket_token` Variable | `RuntimeError` with remediation hint. |
| `git clone` failure (auth, network, branch missing) | `subprocess.CalledProcessError`. Task `retries=2, retry_delay=2min`. Token stays out of logs via `capture_output=True`. |
| Non-UTF-8 markdown file | Warn + skip. Pipeline continues. |
| Markdown file >1 MB | Warn + proceed. |
| Pg connection error | psycopg raises. Per-task retry config catches transient failures. |
| Embedding model load failure | Hard fail; baked image should prevent. |
| Stage-2 mid-batch crash | Per-file transactions isolate; files committed survive; uncommitted ones re-run next time. |
| XCom payload too large (large changeset) | Log a warning at >5 MB. S3-backed XCom is a follow-up. |
| Empty changes list | Early return; no model load, no DB writes. |

**Retry configuration:**

| Task | retries | retry_delay |
|---|---|---|
| `get_repos` | 1 | 30s |
| `process_repo` | 2 | 2min |
| `aggregate_changes` | 1 | 30s |
| `embed_and_upsert` | 2 | 1min |

**Security:**
- Token is injected into the clone URL at task-run time. The tmpdir wipes `.git/config` (which holds the token-bearing remote URL) on task exit.
- `capture_output=True` on `git clone` keeps the URL out of task logs.
- Pg passwords are passed via env vars and never logged.

## 9. Testing strategy

### Pyramid

| Layer | What | Where | CI cost |
|---|---|---|---|
| Unit | Pure functions, no I/O | `tests/unit/` | ms |
| Integration | Real pg+pgvector (testcontainers), fake embedder, fixture local git repos | `tests/integration/` | ~30s |
| DAG-parse | `DagBag` import check | CI step | ms |

### Must-have test cases

**Unit**
- `compute_diff`: empty/empty, all-added, all-deleted, mixed, identical, hash-mismatch.
- `walk_md_files`: nested dirs, symlinks not followed, non-`.md` ignored, POSIX path normalization.
- `_inject_token`: https → tokenized form; non-https raises `ValueError`.
- `split_markdown`: empty, no headings, deep nesting (h1>h2>h3), code fence preservation, prose longer than the token budget, heading prefix counted into the budget.
- `repo_name_from_url`: `.git` suffix stripped, trailing-slash handled.
- `aggregate_changes`: counts roll up per `(repo, branch)`.

**Integration**
- `load_repo_state`: empty for unseen repo; populated for seen; isolated by `(repo, branch)`.
- `upsert_document_with_chunks`: first insert; re-upsert wipes old chunks via FK cascade; empty `chunk_rows` accepted.
- `delete_document`: chunks vanish via cascade.
- `process_repo` against a fixture repo: first run = all-added; unchanged second run = empty diff; edit a file → `modified`; rm a file → `deleted`.
- `embed_and_upsert` end-to-end with the fake embedder: changes-in → `documents` + `chunks` tables match expectation.

### Coverage

≥85% on `dags/docs_rag/**`. Pure modules expected to hit 100%. CI fails below threshold.

## 10. CI pipeline (`.github/workflows/ci.yml`)

Runs on every push and pull request. Required status check on `main`.

Jobs (parallel where possible):

1. **lint** — `ruff check .` + `ruff format --check .`
2. **type** — `mypy dags/`
3. **unit** — `pytest tests/unit -q --cov=dags --cov-fail-under=85`
4. **integration** — `pytest tests/integration -q` (testcontainers pulls the pgvector image)
5. **dag-parse** — `python -c "from airflow.models.dagbag import DagBag; b=DagBag('dags'); assert not b.import_errors, b.import_errors"`

Python: 3.12.
Dependency install: `uv sync --frozen` from `uv.lock`.
Cache: uv's package cache + Docker layer cache for the testcontainers image.

## 11. Future work

- MCP server exposing the index to assistants.
- Query API / CLI to retrieve top-k chunks for a question.
- Additional git hosts (GitHub, GitLab) with their own token shapes.
- Pluggable embedding model (currently hardcoded).
- S3-backed XCom for large changesets.
- Observability beyond Airflow's built-in task logs (metrics, traces).
- Branch-based scheduling once a steady cadence is known (currently manual-trigger only).
