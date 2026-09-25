.PHONY: up down logs install lint format typecheck test test-docker check migrate migration

up:            ## Start Postgres + API (hot reload) in Docker
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f api
install:       ## Local venv for editor/tooling
	uv sync
lint:
	uv run ruff check .
format:
	uv run ruff format . && uv run ruff check . --fix
typecheck:
	uv run mypy app harness tests
test:          ## Needs `docker compose up -d db`
	uv run pytest -q
test-docker:   ## Full suite inside the Linux image (runs the memory-limit test too)
	docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://backend_city:backend_city@db:5432/backend_city_test api python -m pytest -q -p no:cacheprovider
check: lint typecheck test
migrate:
	docker compose exec api alembic upgrade head
migration:     ## make migration m="add lessons"
	uv run alembic revision --autogenerate -m "$(m)"
