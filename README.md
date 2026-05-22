# ragit

Documentation-RAG ingestion pipeline. Crawls a configured set of git repositories, detects added/modified/deleted markdown files, chunks them, embeds the chunks with a local model, and writes them to a Postgres + pgvector store.

See [docs/architecture.md](docs/architecture.md) for component / sequence diagrams and [docs/design.md](docs/design.md) for full design notes (schema, error handling, testing strategy).

## Prerequisites

[`uv`](https://docs.astral.sh/uv/) and Docker. That's it.

## Local setup

```sh
make install
cp .env.example .env
```

Set `AIRFLOW_FERNET_KEY` in `.env`:

```sh
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Airflow UI login: `admin` / `admin`, defined in `docker/admin_password.json`. **Change this file before deploying anywhere that isn't your laptop.**

## Running locally

```sh
make up
```

Airflow standalone is available at <http://localhost:8080>. Login: `admin` / `admin`. Postgres exposes `5432` for inspection.

To set the repo list, open **Admin → Variables → +**, key `docs_rag_repos`, serialize as JSON, value e.g.:

```json
[
  {"url": "https://github.com/foo/public-repo.git"},
  {"url": "https://github.com/me/private.git", "token": "ghp_xxx"},
  {"url": "https://bitbucket.org/team/docs.git", "token": "ATBB...", "branch": "develop"},
  {"url": "https://gitlab.com/proj/docs.git", "token": "glpat-..."}
]
```

Per entry: `url` required (https only, host in `github.com` / `bitbucket.org` / `gitlab.com`); `token` optional (omit for public repos); `branch` optional (defaults to remote HEAD); `name` optional (defaults to URL basename).

Then trigger the DAG `docs_rag_repo_diff` from the Dags page.

## Connecting an LLM client to the MCP server

The MCP server is at `http://localhost:8000/mcp` once `make up` is healthy. Bearer token = `RAGIT_MCP_TOKEN` in `.env`.

### Claude Code

```sh
source .env
claude mcp add --transport http ragit http://localhost:8000/mcp \
  -H "Authorization: Bearer $RAGIT_MCP_TOKEN"
```

Add `--scope user` to register across all projects, `--scope project` to commit a `.mcp.json` to the repo. Verify with `claude mcp list`; inside a session, `/mcp`.

### Codex CLI

Edit `~/.codex/config.toml`:

```toml
experimental_use_rmcp_client = true

[mcp_servers.ragit]
url = "http://localhost:8000/mcp"
bearer_token_env_var = "RAGIT_MCP_TOKEN"
```

Export the token before launching Codex so the env-var lookup resolves:

```sh
source .env && export RAGIT_MCP_TOKEN
codex
```

### Other clients (Claude Desktop, Cursor)

Same endpoint + bearer header. Format varies by client — refer to the client's MCP config docs and use:

- URL: `http://localhost:8000/mcp`
- Transport: streamable HTTP
- Header: `Authorization: Bearer <RAGIT_MCP_TOKEN>`

## Make commands

| Target | Purpose |
|---|---|
| `make install` | Install Python deps and wire git hooks. One-time per clone. |
| `make up` | Start the Airflow + Postgres stack (detached). Uses existing image. |
| `make up-build` | Rebuild the image and start the stack. Use after Dockerfile or dep changes. |
| `make down` | Stop the stack. |
| `make down-v` | Stop the stack and drop the Postgres volume (resets state). |
| `make logs` | Follow Airflow logs. |
| `make build` | Rebuild the Airflow image. |
| `make lint` | `ruff check .` |
| `make format` | `ruff format .` (writes). |
| `make format-check` | `ruff format --check .` |
| `make type` | `mypy dags` |
| `make test` | Full pytest suite (unit + integration). Integration needs Docker for testcontainers. |
| `make test-unit` | Unit tests only. Fast. |
| `make test-integration` | Integration tests only. Spins a real pgvector container. |
| `make ci` | What CI runs: lint, format-check, type, test. |

Work in progress.
