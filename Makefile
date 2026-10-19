.PHONY: lint test test-integration db-up db-reset data split ingest

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

# FinanceBench Questions and PDFs into data/financebench/ (gitignored: CC-BY-NC); reruns skip what's there.
data:
	uv run python -m sec_filings_analyst.financebench

# The committed dev/test Split (needs `make data`); refuses to overwrite an existing version.
split:
	uv run python -m sec_filings_analyst.split

# Embeds and stores every downloaded Document not stored yet (needs make data, make db-up and
# OPENAI_API_KEY in .env). Shows the token count and cost and asks before calling OpenAI.
ingest:
	uv run --env-file .env python -m sec_filings_analyst.ingest
