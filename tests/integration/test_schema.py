import psycopg
import pytest

pytestmark = pytest.mark.integration


def vector(*head):
    """A 1536-dim pgvector literal starting with `head`, zeros after."""
    return "[" + ",".join(map(str, [*head, *[0.0] * (1536 - len(head))])) + "]"


def test_exact_cosine_search_returns_chunks_nearest_first(db):
    (doc_id,) = db.execute(
        "INSERT INTO documents (name, company, doc_type, fiscal_year, page_count)"
        " VALUES ('3M_2018_10K', '3M', '10-K', 2018, 160) RETURNING id"
    ).fetchone()
    # Cosine distance to the query (1, 0): page 3 is 0, page 5 is 1 - 1/sqrt(2), page 7 is 1.
    for page, embedding in [(7, vector(0, 1)), (3, vector(1, 0)), (5, vector(1, 1))]:
        db.execute(
            "INSERT INTO chunks (document_id, page, position, text, token_count, embedding)"
            " VALUES (%s, %s, 0, %s, 3, %s)",
            [doc_id, page, f"text of page {page}", embedding],
        )

    rows = db.execute(
        "SELECT d.name, c.page FROM chunks c JOIN documents d ON d.id = c.document_id"
        " ORDER BY c.embedding <=> %s::vector LIMIT 3",
        [vector(1, 0)],
    ).fetchall()

    assert rows == [("3M_2018_10K", 3), ("3M_2018_10K", 5), ("3M_2018_10K", 7)]


def test_has_no_approximate_nearest_neighbor_index(db):
    ann = db.execute(
        "SELECT indexname FROM pg_indexes WHERE indexdef ~* 'using (hnsw|ivfflat)'"
    ).fetchall()

    assert ann == []


def test_rejects_a_doc_type_that_skipped_normalization(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO documents (name, company, doc_type, fiscal_year, page_count)"
            " VALUES ('3M_2018_10K', '3M', '10k', 2018, 160)"  # FinanceBench's raw form
        )
