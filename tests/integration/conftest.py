import os
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

SCHEMA = Path(__file__).parents[2] / "db" / "schema.sql"
DEV_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/sec_filings"
)
TEST_DB = "sec_filings_test"


@pytest.fixture
def db():
    """A throwaway database with the schema applied; the dev database is never touched."""
    with psycopg.connect(DEV_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    with psycopg.connect(make_conninfo(DEV_URL, dbname=TEST_DB)) as conn:
        conn.execute(SCHEMA.read_text())
        yield conn
    with psycopg.connect(DEV_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE {TEST_DB}")
