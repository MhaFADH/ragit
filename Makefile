install:
	uv sync
	uv run lefthook install

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

type:
	uv run mypy dags mcp_server

test:
	uv run pytest -q

test-unit:
	uv run pytest tests/unit -q

test-integration:
	uv run pytest tests/integration -q

ci: lint format-check type test

up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

down-v:
	docker compose down -v

logs:
	docker compose logs -f

build:
	docker compose build
