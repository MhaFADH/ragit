# ragit

Documentation-RAG ingestion pipeline. Crawls a configured set of git repositories, detects added/modified/deleted markdown files, chunks them, embeds the chunks with a local model, and writes them to a Postgres + pgvector store.

See [docs/design.md](docs/design.md) for the architecture, data flow, and testing strategy.

## Local setup

```sh
uv sync
uv run lefthook install
```

`uv run lefthook install` is a one-time step per clone: it wires the hooks declared in `lefthook.yml` (ruff + mypy on pre-commit, full sweep on pre-push).

Work in progress.
