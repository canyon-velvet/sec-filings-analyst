.PHONY: lint test test-integration db-up db-reset

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

db-up:
	docker compose up -d --wait

# Drops and recreates the schema in the dev database (all data can be rebuilt).
db-reset:
	docker compose exec -T db psql -q -U postgres -d sec_filings -v ON_ERROR_STOP=1 < db/schema.sql
