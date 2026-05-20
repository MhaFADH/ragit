# ragit

Documentation-RAG ingestion pipeline. Crawls a configured set of git repositories, detects added/modified/deleted markdown files, chunks them, embeds the chunks with a local model, and writes them to a Postgres + pgvector store.

See [docs/design.md](docs/design.md) for the architecture, data flow, and testing strategy.

## Local setup

```sh
make install
```

Installs Python deps via `uv sync` and wires git hooks via `lefthook install`. One-time per clone.

## Running locally

```sh
make up
```

Airflow standalone is available at <http://localhost:8080>. Login as `admin` — the random password generated on first boot is written to `simple_auth_manager_passwords.json.generated` inside the airflow container:

```sh
docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Postgres exposes `5432` for inspection.

Follow logs with `make logs`. Stop with `make down` (or `make down-v` to also drop the Postgres volume).

Other shortcuts: `make ci` (full check suite), `make lint`, `make type`, `make test`.

Work in progress.
