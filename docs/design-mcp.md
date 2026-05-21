# ragit MCP — Design

The MCP server exposes the indexed documentation (written by the ingestion DAG) to LLM clients over the [Model Context Protocol](https://modelcontextprotocol.io). It runs as a streamable-HTTP service alongside Airflow + Postgres in `docker-compose.yml`, authenticates with a single bearer token, and surfaces three tools.

For ingestion-side design see [design.md](design.md). For the full architecture map see [architecture.md](architecture.md).

---

## 1. Goals

1. Make the indexed corpus useful: any MCP-capable client can search docs and ask about the index without touching Postgres directly.
2. Deployable. Streamable HTTP transport, bearer auth, fits a real network deployment without rework.
3. Decoupled from ingestion code. The MCP image installs only what it needs (`mcp`, `psycopg`, `pgvector`, `fastembed`, `numpy`). No Airflow.
4. Same hygiene bar as the ingestion side: unit + integration tests, CI gates, comment-light code, narrative in docs.

## 2. Stack

| Concern | Choice |
|---|---|
| Transport | streamable HTTP (deployable, not stdio) |
| Auth | static bearer token (`RAGIT_MCP_TOKEN` env, fail-fast on startup if unset) |
| Embedding model | `BAAI/bge-large-en-v1.5` (must match ingestion — same vector space) |
| Reranker | `BAAI/bge-reranker-base` (cross-encoder, baked into image) |
| Server SDK | `mcp` (official SDK with FastMCP) |
| Postgres driver | `psycopg` v3 (same as ingestion) |
| Tools exposed | `search_docs`, `list_repos`, `index_status` |
| Service placement | new `mcp` service in `docker-compose.yml` |
| Code organization | independent `mcp_server/` package, no imports from `dags/` |

## 3. Repository layout

```
ragit/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py        # FastMCP app, bearer middleware, tool registration
│   ├── search.py        # full pipeline (embed → cosine pool → rerank → MMR)
│   ├── repos.py         # list_repos, index_status
│   ├── db.py            # connect() helper
│   ├── embedder.py      # singleton embedder + reranker (lazy)
│   └── auth.py          # bearer verification middleware
├── docker/
│   └── Dockerfile.mcp   # python:3.12-slim + mcp deps + model bake
├── tests/
│   ├── unit/mcp_server/
│   │   ├── test_auth.py
│   │   ├── test_search.py
│   │   └── test_db.py
│   ├── integration/mcp_server/
│   │   ├── test_search_pipeline.py
│   │   ├── test_repos.py
│   │   └── test_server_http.py
│   └── _fakes/
│       └── fake_reranker.py
├── docker-compose.yml   # adds `mcp` service
└── .env / .env.example  # adds RAGIT_MCP_TOKEN
```

`mcp_server/` does not import from `dags/`. The two services share only the Postgres database (read by MCP, written by Airflow).

## 4. Components

### 4.1 Server (`mcp_server/server.py`)

| Symbol | Responsibility |
|---|---|
| `mcp = FastMCP("ragit")` | Server instance. |
| Bearer middleware | Verifies `Authorization: Bearer <token>` on every request. 401 on missing / mismatch. |
| `@mcp.tool() search_docs(query, top_k=5, repo=None, branch="main")` | Calls `search.search`. Clamps `top_k` to `[1, 50]`. Filters on `branch` (defaults to `"main"` — pass `""` to reach repos ingested without an explicit branch). |
| `@mcp.tool() list_repos()` | Calls `repos.list_repos`. |
| `@mcp.tool() index_status()` | Calls `repos.index_status`. |
| `__main__` | `mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)`. |

### 4.2 Search pipeline (`mcp_server/search.py`)

| Symbol | Responsibility |
|---|---|
| `search(query, *, top_k, repo, branch) -> list[dict]` | Public entry. Runs the four stages below. |
| `_embed_query(query)` | Single-vector embed via `embedder.embed_query`. |
| `_cosine_pool(qvec, *, pool_size, repo)` | pgvector HNSW: `ORDER BY embedding <=> %s LIMIT pool_size`. Returns rows with embeddings attached (MMR needs them). |
| `_rerank(query, candidates)` | Mutates each candidate with `rerank_score` from the cross-encoder. Sorts by rerank desc. On reranker error: log, fall back to cosine order. |
| `_mmr(candidates, top_k, lambda_)` | Greedy MMR diversification. `lambda_ = 0.7`. |
| `_strip_internal(results)` | Drops `embedding` field before returning to client. |

Tunables (module constants, no env knobs):
- `_CANDIDATE_POOL = 20` — wide pool for the reranker.
- `_MMR_LAMBDA = 0.7` — relevance vs diversity.

### 4.3 Discovery tools (`mcp_server/repos.py`)

| Symbol | SQL | Returns |
|---|---|---|
| `list_repos() -> list[dict]` | `SELECT repo, branch, COUNT(DISTINCT file_path) AS file_count FROM documents GROUP BY repo, branch ORDER BY repo, branch` | `[{repo, branch, file_count}]` |
| `index_status() -> list[dict]` | `SELECT d.repo, d.branch, COUNT(DISTINCT d.file_path) AS file_count, COUNT(c.id) AS chunk_count, COALESCE(SUM(c.token_count), 0) AS total_tokens FROM documents d LEFT JOIN chunks c USING (repo, branch, file_path) GROUP BY d.repo, d.branch ORDER BY d.repo, d.branch` | `[{repo, branch, file_count, chunk_count, total_tokens}]` |

### 4.4 Infra (`mcp_server/db.py`, `mcp_server/embedder.py`, `mcp_server/auth.py`)

| File | Responsibility |
|---|---|
| `db.py` | `connect() -> psycopg.Connection` reads `DOCS_RAG_DATABASE_URL`. `RuntimeError` if unset. |
| `embedder.py` | Thread-safe lazy singletons for `TextEmbedding(BGE-large)` + `TextCrossEncoder(BGE-reranker-base)`. `embed_query(query) -> np.ndarray`, `rerank(query, contents) -> list[float]`. |
| `auth.py` | `verify_bearer(headers)` — constant-time compare against `RAGIT_MCP_TOKEN`. Raises 401 on mismatch. Server boot fails fast if env unset. |

### 4.5 Image (`docker/Dockerfile.mcp`)

Base: `python:3.12-slim`. Installs `mcp psycopg[binary] pgvector fastembed numpy`. Warms both models at build time so the running container does no network I/O. Copies `mcp_server/` into `/app`. `CMD ["python", "-m", "mcp.server"]`. Expected size ≈ 1.5 GB.

### 4.6 Compose service

```yaml
mcp:
  build:
    context: .
    dockerfile: docker/Dockerfile.mcp
  depends_on:
    postgres:
      condition: service_healthy
  environment:
    DOCS_RAG_DATABASE_URL: postgresql://docs_rag:docs_rag@postgres:5432/docs_rag
    RAGIT_MCP_TOKEN: ${RAGIT_MCP_TOKEN}
  ports:
    - "8000:8000"
```

`.env` adds `RAGIT_MCP_TOKEN`. `.env.example` ships with a clearly-fake placeholder + instructions to generate a real one (`openssl rand -hex 32`).

## 5. Data flow

### `search_docs(query, top_k, repo, branch)`

```
HTTP POST /mcp ─ Authorization: Bearer <token>
  └─ auth.verify_bearer            # 401 if missing/mismatch
search.search(query, top_k, repo, branch)
  ├─ embedder.embed_query(query)   → np.ndarray (1024)
  ├─ _cosine_pool                  → top 20 chunks from pgvector
  │      SELECT … FROM chunks
  │      WHERE [repo = %s AND] branch = %s
  │      ORDER BY embedding <=> %s LIMIT 20
  ├─ _rerank                       → mutates candidates w/ rerank_score
  ├─ _mmr                          → top_k diversified
  └─ _strip_internal               → drop embedding column
```

### `list_repos()` and `index_status()`

Pure SQL aggregates against `documents` (+ `chunks` for `index_status`). No model load.

### Lifecycle

| Event | Cost |
|---|---|
| Container boot | ~1 s (FastAPI/uvicorn boot). Models NOT loaded yet. |
| First `search_docs` | Loads embedder (~3 s) + reranker (~2 s), then serves. |
| First `list_repos` / `index_status` | No model load. Just one SQL query. |
| Subsequent calls | Models reused (in-process singletons). |
| Container restart | Cold start again. |

## 6. Configuration

| Key | Where | Purpose |
|---|---|---|
| `DOCS_RAG_DATABASE_URL` | `.env` (compose env) | psycopg connection string for the app DB. Reused by ingestion. |
| `RAGIT_MCP_TOKEN` | `.env` (compose env) | Bearer token shared with clients. Generate via `openssl rand -hex 32`. |

## 7. Error handling, auth, security

| Failure | Response |
|---|---|
| `RAGIT_MCP_TOKEN` unset | Server fails fast at startup. Logged once. No insecure default. |
| Missing / wrong bearer | 401 with empty body. Constant-time compare. No token echo. |
| `DOCS_RAG_DATABASE_URL` unset | Tool raises `RuntimeError` with remediation hint. |
| Postgres connection error | psycopg `OperationalError` → MCP tool error. No internal retry. Client re-calls. |
| Embedder model load failure | Hard fail at tool-call time. Baked image should prevent. Logged. |
| Empty `chunks` table | `search_docs` returns `[]`. Not an error. |
| `top_k` ≤ 0 or > 50 | Clamped into `[1, 50]`. Log warning if user requested > 50. |
| Reranker error | Caught + logged. Tool falls back to cosine order, still returns results. |
| Token in errors / logs | Never logged. Never echoed in error bodies. |

**Security notes:**
- TLS termination is the deployer's responsibility (reverse proxy: Traefik / nginx). Out of v1 scope.
- Bearer = single shared secret. Multi-user identity (OAuth) is future work.
- Tool args go to psycopg as parameters — no SQL injection.
- Returned `content` is verbatim markdown. If indexed docs contain prompt-injection text, the LLM client receives it. Out of MCP's responsibility.

**Logging:** INFO with tool name, top_k, repo filter, result count, latency. No query content, no tokens. Structured.

## 8. Testing strategy

| Layer | What | Where |
|---|---|---|
| Unit | Pure functions, mocked deps, bearer parsing | `tests/unit/mcp_server/` |
| Integration | Full pipeline against real pg via testcontainers; fake embedder + fake reranker | `tests/integration/mcp_server/` |
| Transport | Boot server in-process, hit `/mcp` with `httpx`, verify auth + tool calls | `tests/integration/mcp_server/test_server_http.py` |

Reuses ingestion's `docs_rag_database_url` session fixture + `pg_conn` per-test fixture. Adds `populated_pg` that seeds a small corpus via `upsert_document_with_chunks` so search/list_repos have real data.

Fake reranker (in `tests/_fakes/fake_reranker.py`): deterministic scores from hash of `(query, content)`. Skips loading the cross-encoder in CI.

Must-have cases:
- **Auth:** missing header → 401; wrong scheme → 401; matching token → pass; mismatch → 401; server boot fails when `RAGIT_MCP_TOKEN` unset.
- **Search:** empty DB → `[]`; `repo` filter restricts; MMR collapses duplicates; reranker exception falls back to cosine.
- **Discovery:** `list_repos` empty / populated; `index_status` joins + sums correctly.
- **HTTP transport:** server boots; 401 without bearer; 200 with bearer + tool returns valid JSON-RPC.

CI: tests folded into existing `unit` and `integration` jobs in `.github/workflows/ci.yml` — pytest discovers `tests/unit/mcp_server/` and `tests/integration/mcp_server/` automatically.

Coverage target: ≥85% on `mcp_server/**`. Pure modules expected at 100%.

## 9. Future work

- TLS termination via deploy-time reverse proxy (Traefik / nginx).
- OAuth 2.1 (MCP spec) for multi-user identity.
- `last_indexed_at` timestamp column in `documents` so `index_status` can show freshness.
- Streaming results for very large `top_k`.
- Pluggable reranker / embedder model selection.
- Independent compose file (`docker-compose.mcp.yml`) so MCP can run against a remote `docs_rag` DB without spinning Airflow locally.
